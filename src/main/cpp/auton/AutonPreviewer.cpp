//====================================================================================================================================================
// Copyright 2025 Lake Orion Robotics FIRST Team 302
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

#include <string>

// FRC Includes
#include "wpi/math/geometry/Pose2d.hpp"
#include "wpi/math/geometry/Rotation2d.hpp"
#include "wpi/math/kinematics/ChassisVelocities.hpp"
#include "wpi/math/trajectory/Trajectory.hpp"
#include "wpi/units/angle.hpp"
#include "wpi/units/angular_velocity.hpp"
#include "wpi/units/velocity.hpp"

// Team302 Includes
#include "auton/AutonPreviewer.h"
#include "auton/AutonSelector.h"
#include "auton/PrimitiveEnums.h"
#include "auton/PrimitiveParams.h"
#include "auton/PrimitiveParser.h"
#include "auton/drivePrimitives/AutonUtils.h"
#include "chassis/ChassisConfigMgr.h"
#include "chassis/generated/CommandSwerveDrivetrain.h"
#include "utils/logging/debug/Logger.h"
#include "wpi/framework/RobotBase.hpp"

// Thirdparty includes
using std::string;
using wpi::math::ChassisVelocities;
using wpi::math::Rotation2d;
using wpi::math::Trajectory;

AutonPreviewer::AutonPreviewer(CyclePrimitives *cyclePrims) : m_selector(cyclePrims->GetAutonSelector()),
                                                              m_prevChoice(""),
                                                              m_field(DragonField::GetInstance())
{
}

void AutonPreviewer::CheckCurrentAuton()
{

    std::string currentChoice = m_selector->GetSelectedAutoFile();

    // If the robot is not disabled, clear the field and return
    if (!wpi::RobotBase::IsDisabled())
    {
        m_field->ResetField();
        m_prevChoice = ""; // Optional: force re-population once disabled again
        return;
    }

    if (currentChoice != m_prevChoice)
    {
        PopulateField();
        m_prevChoice = currentChoice;
    }
}

void AutonPreviewer::PopulateField()
{
    auto trajectories = GetTrajectories();
    m_field->ResetField();
    for (unsigned int i = 0; i < trajectories.size(); i++)
    {
        m_field->AddTrajectory("traj" + std::to_string(i), trajectories[i]);
    }
}

std::vector<wpi::math::Trajectory> AutonPreviewer::GetTrajectories()
{

    std::vector<wpi::math::Trajectory> trajectories;

    /* SystemCore TO DO: uncomment when choreo is added back as a dependency
    wpi::math::ChassisVelocities speeds;
    speeds.vx = wpi::units::velocity::feet_per_second_t(0.0);
    speeds.vy = wpi::units::velocity::feet_per_second_t(0.0);
    speeds.omega = wpi::units::angular_velocity::degrees_per_second_t(0.0);

    wpi::math::Rotation2d heading(wpi::units::angle::degree_t(0.0));

    auto chassis = ChassisConfigMgr::GetInstance()->GetSwerveChassis();

    if (chassis != nullptr)
    {
        auto params = PrimitiveParser::ParseXML(m_selector->GetSelectedAutoFile());

        for (auto param : params)
        {
            std::vector<wpi::math::Trajectory::State> states;

            if (param->GetID() == PRIMITIVE_IDENTIFIER::TRAJECTORY_DRIVE)
            {
                auto pathname = param->GetTrajectoryName();
                auto path = AutonUtils::GetTrajectoryFromPathFile(pathname);
                if (path.has_value())
                {
                    auto wpi::math::Trajectory = path.value();
                    auto endstate = wpi::math::Trajectory.GetFinalSample().value();
                    heading = endstate.heading;
                    speeds.vx = endstate.vx;
                    speeds.vy = endstate.vy;

                    auto samples = wpi::math::Trajectory.samples;
                    for (auto sample : samples)
                    {
                        wpi::math::Trajectory::State state;
                        state.t = sample.timestamp;
                        state.acceleration = wpi::units::math::sqrt(sample.ax * sample.ax + sample.ay * sample.ay);
                        state.velocity = wpi::units::math::sqrt(sample.vx * sample.vx + sample.vy * sample.vy);
                        state.pose = sample.GetPose();
                        state.curvature = wpi::units::curvature_t(0.1);

                        states.emplace_back(state);
                    }
                    trajectories.emplace_back(states);
                }
            }
        }
    }
        */
    return trajectories;
}