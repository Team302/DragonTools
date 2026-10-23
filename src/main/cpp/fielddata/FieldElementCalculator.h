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

// c++ includes
#include <map>

#include <fielddata/FieldConstants.h>
#include <wpi/math/geometry/Pose3d.hpp>

struct TransformToPose
{
    FieldConstants::FIELD_ELEMENT referencePose;
    wpi::math::Transform3d transform;
};

class FieldElementCalculator
{

public:
    void CalcPositionsForField(robin_hood::unordered_map<FieldConstants::FIELD_ELEMENT, wpi::math::Pose3d> &fieldConstantsPoseMap);

private:
    void InitializeTransforms();

    static constexpr wpi::units::length::inch_t m_xDistanceHubCenter{-23.5};
    static constexpr wpi::units::length::inch_t m_zDistanceHubCenter{0.0};
    static constexpr wpi::units::length::inch_t m_xDistanceTowerStickOffsetLeft{45.0};
    static constexpr wpi::units::length::inch_t m_yDistanceTowerStickOffsetLeft{-19.5};
    static constexpr wpi::units::length::inch_t m_xDistanceTowerStickOffsetRight{45.0};
    static constexpr wpi::units::length::inch_t m_yDistanceTowerStickOffsetRight{19.5};
    static constexpr wpi::units::length::inch_t m_xDistanceTowerStickOffsetCenter{45.0};
    static constexpr wpi::units::length::inch_t m_xDistanceDepotOffsetCenter{27.0};
    static constexpr wpi::units::length::inch_t m_yDistanceDepotOffsetCenter{87.31};
    static constexpr wpi::units::length::inch_t m_zDistanceDepotOffsetCenter{-21.75};
    static constexpr wpi::units::length::inch_t m_xDistanceDepotOffsetLeft{13.5};
    static constexpr wpi::units::length::inch_t m_yDistanceDepotOffsetLeft{108.31};
    static constexpr wpi::units::length::inch_t m_zDistanceDepotOffsetLeft{-21.75};
    static constexpr wpi::units::length::inch_t m_xDistanceDepotOffsetRight{13.5};
    static constexpr wpi::units::length::inch_t m_yDistanceDepotOffsetRight{66.31};
    static constexpr wpi::units::length::inch_t m_zDistanceDepotOffsetRight{-21.75};
    static constexpr wpi::units::length::inch_t m_depotPassingTargetXOffset{40.0};
    static constexpr wpi::units::length::inch_t m_depotPassingTargetYOffset{220.0};
    static constexpr wpi::units::length::inch_t m_depotPassingTargetZOffset{-21.75};
    static constexpr wpi::units::length::inch_t m_outpostPassingTargetXOffset{40.0};
    static constexpr wpi::units::length::inch_t m_outpostPassingTargetYOffset{40.0};
    static constexpr wpi::units::length::inch_t m_outpostPassingTargetZOffset{-21.75};
    static constexpr wpi::units::length::inch_t m_xNoOffset{0.0};
    static constexpr wpi::units::length::inch_t m_yNoOffset{0.0};
    static constexpr wpi::units::length::inch_t m_zNoOffset{0.0};

    // Robot is 34" from front to back
    wpi::math::Transform3d m_halfRobotTransform = wpi::math::Transform3d(
        wpi::math::Translation3d(
            wpi::units::length::inch_t(17), // 16
            wpi::units::length::inch_t(0.0),
            wpi::units::length::inch_t(0.0)),
        wpi::math::Rotation3d());

    // other transforms
    wpi::math::Transform3d m_noTransform = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xNoOffset,
            m_yNoOffset,
            m_zNoOffset),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcHubCenter = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceHubCenter,
            m_yNoOffset,
            m_zDistanceHubCenter),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcTowerLeftStick = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceTowerStickOffsetLeft,
            m_yDistanceTowerStickOffsetLeft,
            m_zNoOffset),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcTowerRightStick = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceTowerStickOffsetRight,
            m_yDistanceTowerStickOffsetRight,
            m_zNoOffset),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcTowerCenter = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceTowerStickOffsetCenter,
            m_yNoOffset,
            m_zNoOffset),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcDepoOffsetCenter = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceDepotOffsetCenter,
            m_yDistanceDepotOffsetCenter,
            m_zDistanceDepotOffsetCenter),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcDepoOffsetLeft = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceDepotOffsetLeft,
            m_yDistanceDepotOffsetLeft,
            m_zDistanceDepotOffsetLeft),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcDepoOffsetRight = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_xDistanceDepotOffsetRight,
            m_yDistanceDepotOffsetRight,
            m_zDistanceDepotOffsetRight),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcDepoPassingTarget = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_depotPassingTargetXOffset,
            m_depotPassingTargetYOffset,
            m_depotPassingTargetZOffset),
        wpi::math::Rotation3d());

    wpi::math::Transform3d m_calcOutpostPassingTarget = wpi::math::Transform3d(
        wpi::math::Translation3d(
            m_outpostPassingTargetXOffset,
            m_outpostPassingTargetYOffset,
            m_outpostPassingTargetZOffset),
        wpi::math::Rotation3d());

    robin_hood::unordered_map<FieldConstants::FIELD_ELEMENT, TransformToPose> m_transformCalculatedMap;
    robin_hood::unordered_map<FieldConstants::FIELD_ELEMENT, TransformToPose> m_transformTagsMap;
};