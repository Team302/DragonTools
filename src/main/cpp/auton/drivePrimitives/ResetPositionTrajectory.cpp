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

// C++ Includes
#include <memory>
#include <string>

// Team 302 includes
#include "auton/PrimitiveParams.h"
#include "auton/drivePrimitives/AutonUtils.h"
#include "auton/drivePrimitives/IPrimitive.h"
#include "auton/drivePrimitives/ResetPositionTrajectory.h"

#include "chassis/ChassisConfigMgr.h"
#include "chassis/generated/CommandSwerveDrivetrain.h"
#include "utils/FMSData.h"
#include "utils/logging/debug/Logger.h"
#include "vision/DragonVision.h"

// Third Party Includes

using namespace std;

ResetPositionTrajectory::ResetPositionTrajectory() : IPrimitive()
{
}

void ResetPositionTrajectory::Init(PrimitiveParams *param)
{
    // SystemCore To Do:Enable when choreo is added back as a dependency
    // auto config = ChassisConfigMgr::GetInstance();
    // auto chassis = config != nullptr ? config->GetSwerveChassis() : nullptr;

    // if (chassis != nullptr)
    // {

    //     auto path = AutonUtils::GetTrajectoryFromPathFile(param->GetTrajectoryName());

    //     if (path.has_value())
    //     {
    //         auto initialPose = path.value().GetInitialPose();
    //         if (initialPose)
    //         {
    //             // Check to see if current pose is within 2 meters (distanceThreshold) of the centerline (centerline), if it isn't, reset pose with pathplanner/choreo
    //             auto actualPose = chassis->GetPose();
    //             const wpi::units::length::meter_t poseDiff = wpi::units::math::abs(actualPose.X() - m_centerline);
    //             bool poseNeedsUpdating = poseDiff > m_distanceThreshold;

    //             if (poseNeedsUpdating)
    //             {
    //                 ResetPose(initialPose.value());
    //             }
    //         }
    //     }
    // }
}

void ResetPositionTrajectory::ResetPose(wpi::math::Pose2d pose)
{
    auto config = ChassisConfigMgr::GetInstance();
    auto chassis = config != nullptr ? config->GetSwerveChassis() : nullptr;

    if (chassis != nullptr)
    {
        chassis->ResetPose(pose);
    }
}

void ResetPositionTrajectory::Run()
{
}

bool ResetPositionTrajectory::IsDone()
{
    return true;
}