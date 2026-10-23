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

// FRC Includes
#include <math.h>

#include "wpi/math/geometry/Pose2d.hpp"

// Team302 Includes
#include "auton/AutonGrid.h"

// Thirdparty includes
#include "wpi/units/math.hpp"

AutonGrid *AutonGrid::m_instance = nullptr; // initialize m_instance as a nullptr

AutonGrid *AutonGrid::GetInstance()
{
    // if m_instance is nullptr then a new instance of AutonGrid is created and returned therefore only leaving one instance of the class
    if (AutonGrid::m_instance == nullptr)
    {
        AutonGrid::m_instance = new AutonGrid();
    }
    return AutonGrid::m_instance;
} // to make the class a singlton

bool AutonGrid::IsPoseInZone(wpi::units::length::meter_t xgrid1, wpi::units::length::meter_t xgrid2, wpi::units::length::meter_t ygrid1, wpi::units::length::meter_t ygrid2, wpi::math::Pose2d robotPose)
// defining IsPoseInZone bool method and pulling in the arguements
{
    // Use min/max to remove dependency on order of x's and y's
    auto xMin = wpi::units::math::min(xgrid1, xgrid2);
    auto xMax = wpi::units::math::max(xgrid1, xgrid2);
    auto yMin = wpi::units::math::min(ygrid1, ygrid2);
    auto yMax = wpi::units::math::max(ygrid1, ygrid2);

    return ((robotPose.X() >= xMin) && (robotPose.X() <= xMax) &&
            (robotPose.Y() >= yMin) && (robotPose.Y() <= yMax));
}
bool AutonGrid::IsPoseInZone(wpi::math::Pose2d circleZonePose, wpi::units::length::inch_t radius, wpi::math::Pose2d robotPose)
{
    // Use squared distance comparison to avoid expensive sqrt in Distance()
    auto dx = circleZonePose.X() - robotPose.X();
    auto dy = circleZonePose.Y() - robotPose.Y();
    auto distSquared = dx * dx + dy * dy;
    auto radiusMeters = wpi::units::length::meter_t(radius);
    return distSquared <= radiusMeters * radiusMeters;
}
