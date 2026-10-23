//====================================================================================================================================================
// Copyright 2026 Lake Orion Robotics FIRST Team 302
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"),
// to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
// and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
// OR OTHER DEALINGS IN THE SOFTWARE.
//====================================================================================================================================================

#include "utils/TargetCalculator.h"
#include "utils/logging/debug/Logger.h"

#include <cmath>

TargetCalculator::TargetCalculator()
{
    m_chassis = ChassisConfigMgr::GetInstance()->GetSwerveChassis();
}

wpi::math::Translation2d TargetCalculator::CalculateVirtualTarget(
    const wpi::math::Translation2d &realTarget,
    wpi::units::time::second_t lookaheadTime) const
{
    // Convert robot-relative speeds to field-relative speeds
    auto fieldVelocity = m_currentChassisVelocities.ToRobotRelative(m_chassisPose.Rotation());

    wpi::units::meter_t offsetX = fieldVelocity.vx * lookaheadTime;
    wpi::units::meter_t offsetY = fieldVelocity.vy * lookaheadTime;

    // Virtual goal = real goal - velocity_offset
    // This compensates for the robot moving toward/away from the goal
    return wpi::math::Translation2d{
        realTarget.X() - offsetX,
        realTarget.Y() - offsetY};
}

wpi::math::Translation2d TargetCalculator::CalculateRotationalMechDelta(wpi::units::time::second_t lookaheadTime) const
{
    wpi::units::degree_t futureHeading = m_chassisPose.Rotation().Degrees() +
                                         wpi::units::degree_t{m_currentChassisVelocities.omega.value() * lookaheadTime.value()};

    wpi::math::Translation2d currentMechOffset = m_mechanismOffset.RotateBy(m_chassisPose.Rotation());
    wpi::math::Translation2d futureMechOffset = m_mechanismOffset.RotateBy(wpi::math::Rotation2d{futureHeading});
    return futureMechOffset - currentMechOffset;
}

wpi::math::Translation2d TargetCalculator::GetMechanismWorldPosition() const
{
    return m_chassisPose.Translation() + m_mechanismOffset.RotateBy(m_chassisPose.Rotation());
}

wpi::units::meter_t TargetCalculator::CalculateDistanceToTarget(wpi::units::time::second_t lookaheadTime)
{
    if (!m_isMoving)
    {
        return m_cachedDistanceToTarget;
    }

    auto robotPosition = wpi::math::Translation2d{m_chassisPose.X(), m_chassisPose.Y()};

    auto realTarget = GetTargetPosition();
    auto targetPos = (lookaheadTime > 0_s) ? CalculateVirtualTarget(realTarget, lookaheadTime) : realTarget;

    m_cachedDistanceToTarget = robotPosition.Distance(targetPos);
    return m_cachedDistanceToTarget;
}

wpi::units::meter_t TargetCalculator::CalculateMechanismDistanceToTarget(wpi::units::time::second_t lookaheadTime)
{
    if (!m_isMoving)
    {
        return m_cachedMechanismDistanceToTarget;
    }

    wpi::math::Translation2d mechanismPos = GetMechanismWorldPosition();

    auto realTarget = GetTargetPosition();
    auto targetPos = (lookaheadTime > 0_s) ? CalculateVirtualTarget(realTarget, lookaheadTime) : realTarget;

    m_cachedMechanismDistanceToTarget = mechanismPos.Distance(targetPos);
    return m_cachedMechanismDistanceToTarget;
}

wpi::units::degree_t TargetCalculator::CalculateAngleToTarget(wpi::units::time::second_t lookaheadTime)
{
    auto realTarget = GetTargetPosition();
    auto targetPos = (lookaheadTime > 0_s) ? CalculateVirtualTarget(realTarget, lookaheadTime) : realTarget;
    wpi::math::Translation2d vectorToTarget = targetPos - m_chassisPose.Translation();

    return vectorToTarget.Angle().Degrees();
}

wpi::units::degree_t TargetCalculator::CalculateMechanismAngleToTarget(wpi::units::time::second_t lookaheadTime)
{
    if (!m_isMoving)
    {
        return m_cachedMechanismAngleToTarget;
    }

    wpi::math::Translation2d mechanismPos = GetMechanismWorldPosition();

    auto realTarget = GetTargetPosition();
    auto targetPos = (lookaheadTime > 0_s) ? CalculateVirtualTarget(realTarget, lookaheadTime) : realTarget;

    wpi::math::Translation2d vectorToTarget = targetPos - mechanismPos;

    m_cachedMechanismAngleToTarget = vectorToTarget.Angle().Degrees();
    return m_cachedMechanismAngleToTarget;
}

void TargetCalculator::SetMechanismOffset(wpi::math::Translation2d offset)
{
    m_mechanismOffset = offset;
}

wpi::math::Pose2d TargetCalculator::GetVirtualTargetPose(
    wpi::units::time::second_t lookaheadTime)
{
    auto realTarget = GetTargetPosition();
    return wpi::math::Pose2d{
        CalculateVirtualTarget(realTarget, lookaheadTime),
        wpi::math::Rotation2d{}};
}

void TargetCalculator::UpdateChassisPose(bool forceUpdate)
{
    m_lastChassisPose = m_chassisPose;

    m_isMoving = m_chassis->IsMoving() || (m_wasMovingCounter <= 50);

    // Update the pose while moving, when forced, or on the one cycle after we stop.
    // The "just stopped" cycle ensures the cache busts once so all callers recompute
    // with zero speeds and the virtual-target offset unwinds back to the real target.
    if (m_chassis != nullptr && (forceUpdate || m_isMoving))
    {
        m_chassisPose = m_chassis->GetPose();
    }

    m_wasMovingCounter = m_isMoving ? 0 : m_wasMovingCounter + 1;
}

void TargetCalculator::UpdateChassisVelocities()
{
    if (m_chassis != nullptr)
    {
        m_currentChassisVelocities = m_chassis->GetState().Velocity;
    }
}

void TargetCalculator::DataLog(uint64_t timestamp)
{
    LogDoubleData(timestamp, m_distanceToTargetPath, m_cachedMechanismDistanceToTarget.value(), "m");
}