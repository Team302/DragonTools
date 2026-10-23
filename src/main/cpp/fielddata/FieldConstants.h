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
#pragma once
#include <filesystem>
#include <iostream>

#include "wpi/math/geometry/Pose2d.hpp"
#include <wpi/math/geometry/Pose3d.hpp>
#include <wpi/math/geometry/Rotation3d.hpp>

#include "RobinHood/robin_hood.h"

#include "fielddata/FieldAprilTagIDs.h"
#include "wpi/apriltag/AprilTagFieldLayout.hpp"

#include "wpi/units/angle.hpp"
#include "wpi/units/base.hpp"

class FieldConstants
{
public:
    static FieldConstants *GetInstance();
    enum class FIELD_ELEMENT
    {
        // 2026 - BLUE APRIL TAGS
        BLUE_HUB_ALLIANCE_CENTER,
        BLUE_HUB_OUTPOST_CENTER,
        BLUE_TOWER_CENTER,
        BLUE_OUTPOST_CENTER,
        BLUE_TRENCH_NEUTRAL_DEPOT,
        BLUE_TRENCH_ALLIANCE_DEPOT,
        BLUE_TRENCH_NEUTRAL_OUTPOST,
        BLUE_TRENCH_ALLIANCE_OUTPOST,
        // 2026 - RED APRIL TAGS
        RED_HUB_ALLIANCE_CENTER,
        RED_HUB_OUTPOST_CENTER,
        RED_TOWER_CENTER,
        RED_OUTPOST_CENTER,
        RED_TRENCH_NEUTRAL_DEPOT,
        RED_TRENCH_ALLIANCE_DEPOT,
        RED_TRENCH_NEUTRAL_OUTPOST,
        RED_TRENCH_ALLIANCE_OUTPOST,
        // 2026 - Blue Calculated Positions
        BLUE_HUB_CENTER,
        BLUE_TOWER_DEPOT_STICK,
        BLUE_TOWER_OUTPOST_STICK,
        BLUE_DEPOT_NEUTRAL_SIDE,
        BLUE_DEPOT_LEFT_SIDE,
        BLUE_DEPOT_RIGHT_SIDE,
        BLUE_DEPOT_PASSING_TARGET,
        BLUE_OUTPOST_PASSING_TARGET,

        // 2026 - Red Calculated Positions
        RED_HUB_CENTER,
        RED_TOWER_DEPOT_STICK,
        RED_TOWER_OUTPOST_STICK,
        RED_DEPOT_NEUTRAL_SIDE,
        RED_DEPOT_LEFT_SIDE,
        RED_DEPOT_RIGHT_SIDE,
        RED_DEPOT_PASSING_TARGET,
        RED_OUTPOST_PASSING_TARGET

    };
    // right is outpost left is depot

    wpi::math::Pose3d GetFieldElementPose(FIELD_ELEMENT element);
    wpi::math::Pose2d GetFieldElementPose2d(FIELD_ELEMENT element);

    wpi::math::Pose3d GetAprilTagPose(FieldAprilTagIDs tag);
    wpi::math::Pose2d GetAprilTagPose2d(FieldAprilTagIDs tag);

private:
    // make a singleton
    static FieldConstants *m_instance;
    std::vector<wpi::apriltag::AprilTag> m_aprilTagVector;
    const std::string m_fieldFilePath = "/home/lvuser/FieldData/output.json";
    // make constructor private
    FieldConstants();
    // make singleton copy constructor private
    FieldConstants(const FieldConstants &) = delete;
    FieldConstants &operator=(const FieldConstants &) = delete;
    wpi::math::Pose3d GetAprilTagPoseFromLayout(int tagID);
    wpi::apriltag::AprilTagFieldLayout m_fieldLayout = wpi::apriltag::AprilTagFieldLayout::LoadField(wpi::apriltag::AprilTagField::k2026RebuiltWelded); // change this guy for andymark field

    void ReadFieldCalibrationData();

    wpi::math::Pose3d m_placeholder = wpi::math::Pose3d();

    robin_hood::unordered_map<FIELD_ELEMENT, wpi::math::Pose3d> fieldConstantsPoseMap;
    std::array<wpi::math::Pose2d, 36> m_fieldConst2dPoses;

    robin_hood::unordered_map<int, wpi::math::Pose3d> m_aprilTagPoseMap;
    std::array<wpi::math::Pose2d, 33> m_aprilTag2dPoses;
};