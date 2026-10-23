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

#include <algorithm>
#include <cmath>
#include <string>

// FRC Includes
#include "auton/drivePrimitives/AutonUtils.h"
#include "chassis/commands/TrajectoryDrive.h"
// #include "choreo/Choreo.h" TO DO: uncomment when choreo is added back as a dependency
#include "state/RobotState.h"
#include "utils/FMSData.h"
#include "utils/PoseUtils.h"
#include "utils/logging/debug/Logger.h"
#include "wpi/driverstation/DriverStation.hpp"
#include "wpi/math/geometry/Pose2d.hpp"
#include "wpi/math/geometry/Rotation2d.hpp"
#include "wpi/system/Timer.hpp"
#include "wpi/units/angle.hpp"
#include "wpi/units/angular_velocity.hpp"
#include "wpi/units/velocity.hpp"

TrajectoryDrive::TrajectoryDrive(
    subsystems::CommandSwerveDrivetrain *chassis) : m_chassis(chassis),
                                                    m_pathName(""),
                                                    // m_trajectoryStates(),
                                                    m_prevPose(),
                                                    m_wasMoving(false),
                                                    m_timer(std::make_unique<wpi::Timer>()),
                                                    m_whyDone("Trajectory isn't finished/Error"),
                                                    m_totalTrajectoryTime(0.0_s)
{
    // This command requires the chassis subsystem
    AddRequirements(m_chassis);
    // Enable continuous input for the heading controller for proper wrap-around
    m_headingController.EnableContinuousInput(-std::numbers::pi, std::numbers::pi);
}

void TrajectoryDrive::Initialize()
{
    /*SystemCore TO DO: uncomment when choreo is added back as a dependency
    m_trajectory = AutonUtils::GetTrajectoryFromPathFile(m_pathName);

    if (m_trajectory.has_value())
    {
        auto wpi::math::Trajectory = m_trajectory.value();
        bool isRedAlliance = FMSData::GetAllianceColor() ==  wpi::Alliance::RED;

        // Check if we should use smart joining based on distance from start
        if (m_chassis != nullptr && !wpi::math::Trajectory.samples.empty())
        {
            auto currentPose = m_chassis->GetPose();
            auto startPose = wpi::math::Trajectory.samples[0].GetPose();
            wpi::units::length::meter_t distanceFromStart = PoseUtils::GetDeltaBetweenPoses(currentPose, startPose);

            // If we're too far from the start, use smart joining with default XY matching
            if (distanceFromStart > m_joinTolerance)
            {
                // Use InitializeWithTrajectory for smart joining logic
                InitializeWithTrajectory(m_trajectory,
                                         isRedAlliance,
                                         TrajectoryMatchStrategy::MATCH_XY,
                                         m_joinTolerance,
                                         0.9); // Default to searching 90% of wpi::math::Trajectory
                return;
            }
        }

        // We're close enough to the start, proceed with normal initialization
        m_trajectoryStates = wpi::math::Trajectory.samples;
        m_totalTrajectoryTime = wpi::math::Trajectory.GetTotalTime();
        m_thresholdTime = m_totalTrajectoryTime * kPercentComplete;
        auto finalPose = wpi::math::Trajectory.GetFinalPose(isRedAlliance);
        m_finalPose = finalPose.has_value() ? finalPose.value() : wpi::math::Pose2d();
        m_startTimeOffset = 0.0_s;
        m_useSmartJoin = false;
        m_isApproachingPath = false;
    }
    else
    {
        m_totalTrajectoryTime = 0_s;
        m_thresholdTime = 0_s;
        m_trajectoryStates.clear();
        m_finalPose = wpi::math::Pose2d();
        m_startTimeOffset = 0.0_s;
        m_useSmartJoin = false;
        m_isApproachingPath = false;
    }

    m_previousPose = wpi::math::Pose2d();
    m_numberOfExecutions = 0;

    // Reset and start the timer when the command begins
    m_timer.get()->Reset();
    m_timer.get()->Start();

    // Reset PID controllers to clear any previous state
    m_xController.Reset();
    m_yController.Reset();
    m_headingController.Reset();
    m_chassisVelocities = m_chassis->GetState().Velocity;
    m_chassisVelocities.omega = wpi::units::angular_velocity::radians_per_second_t(0);

    RobotState::GetInstance()->PublishStateChange(RobotStateChanges::DriveToFinished_Bool, false);
    */
}

/*SystemCore TO DO: uncomment when choreo is added back as a dependency
//------------------------------------------------------------------
/// @brief Choose between forward and reverse trajectories based on closest entry point
/// @details Finds the closest point on both trajectories and returns the one with
///          the closer entry point. Caches the closest point information to avoid
///          redundant calculations when InitializeWithTrajectory is called.
//------------------------------------------------------------------
std::pair<std::optional<choreo::Trajectory<choreo::SwerveSample>>, bool> TrajectoryDrive::SelectBestTrajectory(
    const std::optional<choreo::Trajectory<choreo::SwerveSample>> &forwardTraj,
    const std::optional<choreo::Trajectory<choreo::SwerveSample>> &reverseTraj,
    const wpi::math::Pose2d &currentPose,
    TrajectoryMatchStrategy matchStrategy,
    double maxPercentToJoinForForwardPath,
    double maxPercentToJoinForReversePath)
{
    // If either wpi::math::Trajectory is invalid, use the one that's valid
    if (!forwardTraj.has_value())
    {
        // Cache the reverse wpi::math::Trajectory's closest point
        if (reverseTraj.has_value())
        {
            auto [sample, distance] = FindClosestPointOnTrajectory(reverseTraj.value(), currentPose, matchStrategy, maxPercentToJoinForReversePath);
            m_cachedClosestSample = sample;
            m_cachedClosestDistance = distance;
            m_hasCachedClosestPoint = true;
        }
        return {reverseTraj, false}; // Use reverse if forward doesn't exist
    }
    if (!reverseTraj.has_value())
    {
        // Cache the forward wpi::math::Trajectory's closest point
        auto [sample, distance] = FindClosestPointOnTrajectory(forwardTraj.value(), currentPose, matchStrategy, maxPercentToJoinForForwardPath);
        m_cachedClosestSample = sample;
        m_cachedClosestDistance = distance;
        m_hasCachedClosestPoint = true;
        return {forwardTraj, true}; // Use forward if reverse doesn't exist
    }

    // Find closest points on both trajectories
    auto [forwardSample, distToForward] = FindClosestPointOnTrajectory(
        forwardTraj.value(), currentPose, matchStrategy, maxPercentToJoinForForwardPath);

    auto [reverseSample, distToReverse] = FindClosestPointOnTrajectory(
        reverseTraj.value(), currentPose, matchStrategy, maxPercentToJoinForReversePath);

    // Use the wpi::math::Trajectory with the closer entry point
    bool useForward = distToForward < distToReverse;

    // Cache the selected wpi::math::Trajectory's closest point
    m_cachedClosestSample = useForward ? forwardSample : reverseSample;
    m_cachedClosestDistance = useForward ? distToForward : distToReverse;
    m_hasCachedClosestPoint = true;

    return {useForward ? forwardTraj : reverseTraj, useForward};
}

void TrajectoryDrive::InitializeWithTrajectory(std::optional<choreo::Trajectory<choreo::SwerveSample>> selectedTrajectory, bool generateRedTrajectory, TrajectoryMatchStrategy matchStrategy, wpi::units::length::meter_t distanceTolerance, double maxPercentToJoinPath)
{
    m_trajectory = selectedTrajectory;
    if (m_trajectory.has_value())
    {
        auto wpi::math::Trajectory = m_trajectory.value();
        m_trajectoryStates = wpi::math::Trajectory.samples;
        m_totalTrajectoryTime = wpi::math::Trajectory.GetTotalTime();
        m_thresholdTime = m_totalTrajectoryTime * kPercentComplete;
        auto finalPose = wpi::math::Trajectory.GetFinalPose(generateRedTrajectory);
        m_finalPose = finalPose.has_value() ? finalPose.value() : wpi::math::Pose2d();

        // Smart initialization: Find the closest point in the wpi::math::Trajectory to start from
        if (m_chassis != nullptr && !m_trajectoryStates.empty())
        {
            auto currentPose = m_chassis->GetPose();

            wpi::math::Pose2d closestPose;
            wpi::units::length::meter_t distanceToPath;
            choreo::SwerveSample closestSample;

            // Use cached closest point if available (from SelectBestTrajectory)
            if (m_hasCachedClosestPoint)
            {
                closestSample = m_cachedClosestSample;
                closestPose = wpi::math::Pose2d{m_cachedClosestSample.x, m_cachedClosestSample.y, m_cachedClosestSample.heading};
                distanceToPath = m_cachedClosestDistance;

                // Clear the cache
                m_hasCachedClosestPoint = false;
            }
            else
            {
                // Calculate the closest point if not cached
                size_t closestIndex = FindClosestTrajectoryPoint(currentPose, matchStrategy, distanceTolerance, maxPercentToJoinPath);
                closestSample = m_trajectoryStates[closestIndex];
                closestPose = wpi::math::Pose2d{closestSample.x, closestSample.y, closestSample.heading};
                distanceToPath = CalculateDistance(currentPose, closestPose, matchStrategy);
            }

            // If we're not within tolerance, we need to approach the path first
            if (distanceToPath > distanceTolerance)
            {
                m_useSmartJoin = true;
                m_isApproachingPath = true;
                m_matchStrategy = matchStrategy;
                m_joinTolerance = distanceTolerance;
                m_targetJoinTimestamp = closestSample.timestamp;
                m_targetJoinPose = closestPose;
                m_startTimeOffset = 0.0_s; // Don't start wpi::math::Trajectory timer yet
            }
            else
            {
                // We're already close enough, start following wpi::math::Trajectory from this point
                m_useSmartJoin = false;
                m_isApproachingPath = false;
                m_startTimeOffset = closestSample.timestamp;
            }
        }
        else
        {
            m_useSmartJoin = false;
            m_isApproachingPath = false;
            m_startTimeOffset = 0.0_s;
        }
    }
    else
    {
        m_totalTrajectoryTime = 0_s;
        m_thresholdTime = 0_s;
        m_trajectoryStates.clear();
        m_finalPose = wpi::math::Pose2d();
        m_startTimeOffset = 0.0_s;
        m_useSmartJoin = false;
        m_isApproachingPath = false;
    }
    m_previousPose = wpi::math::Pose2d();
    m_numberOfExecutions = 0;

    // Reset and start the timer when the command begins
    m_timer.get()->Reset();
    m_timer.get()->Start();

    // Reset PID controllers to clear any previous state
    m_xController.Reset();
    m_yController.Reset();
    m_headingController.Reset();
    m_chassisVelocities.vx = 0_mps;
    m_chassisVelocities.vy = 0_mps;
    m_chassisVelocities.omega = wpi::units::angular_velocity::radians_per_second_t(0);

    RobotState::GetInstance()->PublishStateChange(RobotStateChanges::DriveToFinished_Bool, false);
}
*/

void TrajectoryDrive::SetPath(const std::string &pathName)
{
    m_pathName = pathName;
}

void TrajectoryDrive::Execute()
{
    /*SystemCore TO DO: uncomment when choreo is added back as a dependency
if (m_chassis == nullptr || m_trajectoryStates.empty())
{
    return;
}

// Phase 1: Approaching the path (if enabled)
if (m_useSmartJoin && m_isApproachingPath)
{
    auto currentPose = m_chassis->GetPose();
    wpi::units::length::meter_t distanceToTarget = CalculateDistance(currentPose, m_targetJoinPose, m_matchStrategy);

    // Check if we've reached the target join point
    if (distanceToTarget <= m_joinTolerance)
    {
        m_isApproachingPath = false;
        m_startTimeOffset = m_targetJoinTimestamp;
        m_timer.get()->Reset();
        m_timer.get()->Start();
    }
    else
    {
        // Drive toward the join point
        wpi::units::meters_per_second_t vx = 0_mps;
        wpi::units::meters_per_second_t vy = 0_mps;

        if (m_matchStrategy == TrajectoryMatchStrategy::MATCH_Y_ONLY)
        {
            wpi::units::meters_per_second_t yFeedback{m_yController.Calculate(currentPose.Y().value(), m_targetJoinPose.Y().value())};
            vy = yFeedback;
            vx = 0_mps;
        }
        else if (m_matchStrategy == TrajectoryMatchStrategy::MATCH_X_ONLY)
        {
            wpi::units::meters_per_second_t xFeedback{m_xController.Calculate(currentPose.X().value(), m_targetJoinPose.X().value())};
            vx = xFeedback;
            vy = 0_mps;
        }
        else // MATCH_XY
        {
            vx = wpi::units::meters_per_second_t{m_xController.Calculate(currentPose.X().value(), m_targetJoinPose.X().value())};
            vy = wpi::units::meters_per_second_t{m_yController.Calculate(currentPose.Y().value(), m_targetJoinPose.Y().value())};
        }

        wpi::units::radians_per_second_t omega{m_headingController.Calculate(currentPose.Rotation().Radians().value(), m_targetJoinPose.Rotation().Radians().value())};

        m_chassisVelocities.vx = vx;
        m_chassisVelocities.vy = vy;
        m_chassisVelocities.omega = omega;

        m_chassis->SetControl(
            m_driveRequest.WithVelocityX(m_chassisVelocities.vx)
                .WithVelocityY(m_chassisVelocities.vy)
                .WithRotationalRate(m_chassisVelocities.omega)
                .WithForwardPerspective(ctre::phoenix6::swerve::requests::ForwardPerspectiveValue::BlueAlliance));

        return; // Don't follow wpi::math::Trajectory yet
    }
}

// Phase 2: Following the wpi::math::Trajectory
m_elapsedTime = m_timer->Get() + m_startTimeOffset; // Add offset for mid-trajectory starts
if (!m_trajectoryStates.empty())
{
    auto desiredState = m_trajectory.value().SampleAt(m_elapsedTime).value();
    if (m_chassis != nullptr)
    {
        auto currentPose = m_chassis->GetPose();

        wpi::units::meters_per_second_t xFeedback{m_xController.Calculate(currentPose.X().value(), desiredState.x.value())};
        wpi::units::meters_per_second_t yFeedback{m_yController.Calculate(currentPose.Y().value(), desiredState.y.value())};
        wpi::units::radians_per_second_t headingFeedback{m_headingController.Calculate(currentPose.Rotation().Radians().value(), desiredState.heading.value())};

        m_chassisVelocities.vx = desiredState.vx + xFeedback;
        m_chassisVelocities.vy = desiredState.vy + yFeedback;
        m_chassisVelocities.omega = desiredState.omega + headingFeedback;
    }
}

m_chassis->SetControl(
    m_driveRequest.WithVelocityX(m_chassisVelocities.vx)
        .WithVelocityY(m_chassisVelocities.vy)
        .WithRotationalRate(m_chassisVelocities.omega)
        .WithForwardPerspective(ctre::phoenix6::swerve::requests::ForwardPerspectiveValue::BlueAlliance));
m_numberOfExecutions++;
*/
}

bool TrajectoryDrive::IsFinished()
{
    /*SystemCore TO DO: uncomment when choreo is added back as a dependency
if (m_trajectoryStates.empty())
{
    m_whyDone = "Trajectory states are empty";
    Logger::GetLogger()->LogData(LOGGER_LEVEL::PRINT, "", "why done", m_whyDone);
    return true;
}
else if (m_chassis == nullptr)
{
    m_whyDone = "Chassis is null";
    Logger::GetLogger()->LogData(LOGGER_LEVEL::PRINT, "", "why done", m_whyDone);
    return true;
}
else if (m_useSmartJoin && m_isApproachingPath)
{
    return false;
}

auto currentPose = m_chassis->GetPose();

Logger::GetLogger()->LogData(LOGGER_LEVEL::PRINT, "TrajectoryDrive", "current time", m_elapsedTime.value());
Logger::GetLogger()->LogData(LOGGER_LEVEL::PRINT, "TrajectoryDrive", "total time", m_totalTrajectoryTime.value());

if (m_elapsedTime > m_thresholdTime && m_numberOfExecutions >= kMinExecutions) // avoids a division every loop
{
    auto isSamePose = PoseUtils::IsSamePose(currentPose, m_finalPose, kPositionTolerance, kHeadingTolerance);
    Logger::GetLogger()->LogData(LOGGER_LEVEL::PRINT, "TrajectoryDrive", "is same pose?", isSamePose);
    if (isSamePose)
    {
        // previously also compared the robot's velocity to a tolerance of 1.5 m/s
        // right now skipping this because it doesn't make sense to me but here
        // is where to add it in (and if we do we should compare the squares to the
        // 1.5^2 to avoid the sqrt calculation)
        m_whyDone = "Robot is at the target pose";
        return true;
    }
    else if (PoseUtils::IsSamePose(currentPose, m_previousPose, kPositionTolerance, kHeadingTolerance))
    {
        m_whyDone = "Robot is not moving but is not at the target pose";
        return true;
    }
    m_whyDone = "Robot is not at the target pose";
    m_previousPose = currentPose; // update previous pose for next loop's comparison
}
return false;
*/
    return true; // Temporary return value to allow compilation without choreo dependency
}

void TrajectoryDrive::End(bool interrupted)
{
    // When the command ends (or is interrupted), stop the robot.
    m_chassis->SetControl(swerve::requests::SwerveDriveBrake{});
}

/*SystemCore TO DO: uncomment when choreo is added back as a dependency
//------------------------------------------------------------------
/// @brief Find the closest point in the wpi::math::Trajectory to the robot's current position
/// @details Uses the specified match strategy to find the optimal starting point
///          in the wpi::math::Trajectory. This allows the robot to join the wpi::math::Trajectory at
///          the most appropriate point rather than always starting from the beginning.
///
///          For MATCH_Y_ONLY: Finds the wpi::math::Trajectory point closest to robot's current X,
///                            then picks the one with closest Y at that X position
///          For MATCH_X_ONLY: Finds the wpi::math::Trajectory point closest to robot's current Y,
///                            then picks the one with closest X at that Y position
///          For MATCH_XY: Finds the point with minimum Euclidean distance
//------------------------------------------------------------------
size_t TrajectoryDrive::FindClosestTrajectoryPoint(const wpi::math::Pose2d &currentPose, TrajectoryMatchStrategy matchStrategy, wpi::units::length::meter_t tolerance, double maxPercentToJoinPath) const
{
    if (!m_trajectory.has_value() || m_trajectoryStates.empty())
    {
        return 0;
    }

    // Use the helper method to find the closest point
    auto [closestSample, distance] = FindClosestPointOnTrajectory(
        m_trajectory.value(), currentPose, matchStrategy, maxPercentToJoinPath);

    // Find the index of this sample in our wpi::math::Trajectory states
    // We need to search for the matching sample
    size_t closestIndex = 0;
    for (size_t i = 0; i < m_trajectoryStates.size(); ++i)
    {
        const auto &sample = m_trajectoryStates[i];
        // Compare timestamps to find the exact sample
        if (sample.timestamp == closestSample.timestamp)
        {
            closestIndex = i;
            break;
        }
    }

    return closestIndex;
}

//------------------------------------------------------------------
/// @brief Find the closest point on a given wpi::math::Trajectory to a specific pose
/// @details Uses std::min_element with custom comparators based on match strategy.
///          Searches only the first maxPercentToJoinPath of the wpi::math::Trajectory to avoid
///          selecting end points when the robot is already near the path.
//------------------------------------------------------------------
std::pair<choreo::SwerveSample, wpi::units::length::meter_t> TrajectoryDrive::FindClosestPointOnTrajectory(
    const choreo::Trajectory<choreo::SwerveSample> &trajectory,
    const wpi::math::Pose2d &currentPose,
    TrajectoryMatchStrategy matchStrategy,
    double maxPercentToJoinPath) const
{
    const auto &samples = wpi::math::Trajectory.samples;

    if (samples.empty())
    {
        // Return a default sample at origin with max distance
        return {choreo::SwerveSample{}, wpi::units::meter_t{std::numeric_limits<double>::max()}};
    }

    // Limit search to first maxPercentToJoinPath of wpi::math::Trajectory
    auto searchEndIt = std::next(samples.begin(),
                                 static_cast<size_t>(samples.size() * maxPercentToJoinPath));

    choreo::SwerveSample closestSample;

    if (matchStrategy == TrajectoryMatchStrategy::MATCH_Y_ONLY)
    {
        // For Y-only matching: find the point closest in X, then with minimum Y distance at that X
        auto it = std::min_element(samples.begin(), searchEndIt,
                                   [&currentPose](const choreo::SwerveSample &a, const choreo::SwerveSample &b)
                                   {
                                       auto yDistA = wpi::units::math::abs(a.y - currentPose.Y());
                                       auto yDistB = wpi::units::math::abs(b.y - currentPose.Y());
                                       auto xDistA = wpi::units::math::abs(a.x - currentPose.X());
                                       auto xDistB = wpi::units::math::abs(b.x - currentPose.X());

                                       // If X distances are similar (within 0.1m), prefer the one with smaller Y distance
                                       // Otherwise, prefer the one with smaller X distance
                                       constexpr auto kXWindow = 0.1_m;
                                       if (wpi::units::math::abs(xDistA - xDistB) < kXWindow)
                                       {
                                           return yDistA < yDistB;
                                       }
                                       return xDistA < xDistB;
                                   });

        closestSample = *it;
    }
    else if (matchStrategy == TrajectoryMatchStrategy::MATCH_X_ONLY)
    {
        // For X-only matching: find the point closest in Y, then with minimum X distance at that Y
        auto it = std::min_element(samples.begin(), searchEndIt,
                                   [&currentPose](const choreo::SwerveSample &a, const choreo::SwerveSample &b)
                                   {
                                       auto xDistA = wpi::units::math::abs(a.x - currentPose.X());
                                       auto xDistB = wpi::units::math::abs(b.x - currentPose.X());
                                       auto yDistA = wpi::units::math::abs(a.y - currentPose.Y());
                                       auto yDistB = wpi::units::math::abs(b.y - currentPose.Y());

                                       // If Y distances are similar (within 0.1m), prefer the one with smaller X distance
                                       // Otherwise, prefer the one with smaller Y distance
                                       constexpr auto kYWindow = 0.1_m;
                                       if (wpi::units::math::abs(yDistA - yDistB) < kYWindow)
                                       {
                                           return xDistA < xDistB;
                                       }
                                       return yDistA < yDistB;
                                   });

        closestSample = *it;
    }
    else // MATCH_XY
    {
        // For XY matching: find the point with minimum Euclidean distance
        auto it = std::min_element(samples.begin(), searchEndIt,
                                   [&currentPose](const choreo::SwerveSample &a, const choreo::SwerveSample &b)
                                   {
                                       wpi::math::Pose2d poseA{a.x, a.y, a.heading};
                                       wpi::math::Pose2d poseB{b.x, b.y, b.heading};
                                       auto distA = PoseUtils::GetDeltaBetweenPoses(currentPose, poseA);
                                       auto distB = PoseUtils::GetDeltaBetweenPoses(currentPose, poseB);
                                       return distA < distB;
                                   });

        closestSample = *it;
    }

    // Calculate the distance to the closest sample
    wpi::math::Pose2d closestPose{closestSample.x, closestSample.y, closestSample.heading};
    wpi::units::length::meter_t distance = CalculateDistance(currentPose, closestPose, matchStrategy);

    return {closestSample, distance};
}
*/

//------------------------------------------------------------------
/// @brief Calculate distance between two poses based on match strategy
/// @details Supports three different matching strategies:
///          - MATCH_Y_ONLY: Only considers Y coordinate difference (for horizontal paths)
///          - MATCH_X_ONLY: Only considers X coordinate difference (for vertical paths)
///          - MATCH_XY_EUCLIDEAN: Uses full 2D Euclidean distance (default)
//------------------------------------------------------------------
wpi::units::length::meter_t TrajectoryDrive::CalculateDistance(const wpi::math::Pose2d &pose1, const wpi::math::Pose2d &pose2, TrajectoryMatchStrategy matchStrategy) const
{
    wpi::units::length::meter_t dx = pose1.X() - pose2.X();
    wpi::units::length::meter_t dy = pose1.Y() - pose2.Y();

    switch (matchStrategy)
    {
    case TrajectoryMatchStrategy::MATCH_Y_ONLY:
        return wpi::units::math::abs(dy);

    case TrajectoryMatchStrategy::MATCH_X_ONLY:
        return wpi::units::math::abs(dx);

    case TrajectoryMatchStrategy::MATCH_XY:
    default:
        return PoseUtils::GetDeltaBetweenPoses(pose1, pose2);
    }
}