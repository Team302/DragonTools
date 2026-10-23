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
// FRC Includes
#include "wpi/math/geometry/Pose2d.hpp"
// Team302 Includes

// Thirdparty includes
class AutonGrid
{
public:
    static AutonGrid *GetInstance();

    bool IsPoseInZone(wpi::units::length::meter_t xgrid1, wpi::units::length::meter_t xgrid2, wpi::units::length::meter_t ygrid1, wpi::units::length::meter_t ygrid2, wpi::math::Pose2d robotPose);
    bool IsPoseInZone(wpi::math::Pose2d circleZonePose, wpi::units::length::inch_t radius, wpi::math::Pose2d robotPose);

private:
    AutonGrid() = default;
    ~AutonGrid() = default;
    static AutonGrid *m_instance;
    wpi::units::length::foot_t m_gridRes = wpi::units::length::foot_t(1.0);
};