
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

#include <memory>

#include "state/IRobotStateChangeSubscriber.h"
#include "utils/DragonField.h"
#include "utils/logging/signals/DragonDataLogger.h"
#include "vision/DragonVisionPoseEstimatorStruct.h"
#include "vision/Questnavlib/QuestNav.h"
#include "wpi/math/geometry/Pose2d.hpp"
#include "wpi/math/geometry/Pose3d.hpp"
#include "wpi/math/geometry/Transform3d.hpp"
#include "wpi/nt/NetworkTable.hpp"
#include "wpi/smartdashboard/SendableChooser.hpp"
#include "wpi/smartdashboard/SmartDashboard.hpp"

class DragonQuest : public IRobotStateChangeSubscriber, public DragonDataLogger
{
public:
    DragonQuest(
        wpi::units::length::inch_t mountingXOffset, /// <I> x offset of Quest from robot center (forward relative to robot)
        wpi::units::length::inch_t mountingYOffset, /// <I> y offset of Quest from robot center (left relative to robot)
        wpi::units::length::inch_t mountingZOffset, /// <I> z offset of Quest from robot center (up relative to robot)
        wpi::units::angle::degree_t mountingPitch,  /// <I> - Pitch of Quest
        wpi::units::angle::degree_t mountingYaw,    /// <I> - Yaw of Quest
        wpi::units::angle::degree_t mountingRoll    /// <I> - Roll of Quest
    );
    void DataLog(uint64_t timestamp) override;

    bool HealthCheck() { return m_questNav.IsConnected(); };

    DragonVisionPoseEstimatorStruct GetPoseEstimate();

    void AttemptSetRobotPose(const wpi::math::Pose2d &pose);

    void Periodic();

    void NotifyStateUpdate(RobotStateChanges::StateChange change, bool value) override;

private:
    DragonQuest() = delete;

    /// @brief Read new pose frames from QuestNav, apply mounting transform, and cache the latest 2D pose.
    void GetEstimatedPose();

    /// @brief Read dashboard choosers and update m_isQuestEnabled.
    void HandleDashboard();

    /// @brief Apply the robot-to-Quest mounting offset and send a pose-reset command via QuestNav.
    void SetRobotPose(const wpi::math::Pose2d &pose);

    /// @brief Log status data to the dashboard for debugging and diagnostics.
    void LogDashboardData();

    /// @brief Convert a Quest wpi::math::Pose3d to a robot wpi::math::Pose3d by applying the inverse mounting transform.
    wpi::math::Pose3d QuestPoseToRobotPose3d(const wpi::math::Pose3d &questPose) const;

    /// @brief Convert a robot wpi::math::Pose3d to a Quest wpi::math::Pose3d by applying the mounting transform.
    wpi::math::Pose3d RobotPose3dToQuestPose(const wpi::math::Pose3d &robotPose) const;

    // ── QuestNav library instance (handles all NT / protobuf communication) ──
    QuestNav m_questNav;

    /// @brief NetworkTables instance for logging debug data to the dashboard.
    std::shared_ptr<wpi::nt::NetworkTable> m_debugData;

    // ── Mounting offsets ──
    wpi::units::length::inch_t m_mountingXOffset;
    wpi::units::length::inch_t m_mountingYOffset;
    wpi::units::length::inch_t m_mountingZOffset;
    wpi::units::angle::degree_t m_mountingPitch;
    wpi::units::angle::degree_t m_mountingYaw;
    wpi::units::angle::degree_t m_mountingRoll;

    /// 3D transform from robot centre to Quest mounting location.
    wpi::math::Transform3d m_robotToQuestTransform;

    // ── Dashboard choosers ──
    wpi::SendableChooser<bool> m_questEnabledChooser;
    wpi::SendableChooser<bool> m_questEndgameEnabledChooser;

    // ── State flags ──
    bool m_hasReset = false;
    bool m_isQuestEnabled = false;
    bool m_isClimbMode = false;

    // ── Standard deviations for pose estimator ──
    static constexpr double m_stdxy{0.02};
    static constexpr double m_stddeg{0.035};

    // ── Cached latest pose ──
    wpi::math::Pose3d m_lastCalculatedPose;
    wpi::units::time::second_t m_lastPoseTimestamp{0.0};

    /// wpi::math::Pose2d to reset to (held until connection is available).
    wpi::math::Pose2d m_poseReset;

    /// Counter for throttling pose resets (only set every 3rd call).
    int m_poseResetCounter = 0;

    // ── Field visualisation ──
    DragonField *m_field = nullptr;

    // logging strings

    static constexpr std::string_view m_questHasResetPath = "/Quest/QuestHasReset";
    static constexpr std::string_view m_questIsEnabledPath = "/Quest/IsQuestEnabled";
    static constexpr std::string_view m_questPosePath = "/Quest/QuestPose3d";
    static constexpr std::string_view m_questIsConnectedPath = "Quest/QuestConnected";
    static constexpr std::string_view m_questIsGoofyPath = "Quest/QuestIsGoofy";
    static constexpr std::string_view m_questBatteryPath = "Quest/QuestBatteryPercent";
    static constexpr std::string_view m_questFrameCountPath = "Quest/QuestFrameCount";
    static constexpr std::string_view m_questTrackingLostCountPath = "Quest/QuestTrackingLostCount";
    static constexpr std::string_view m_questAppTimestampPath = "Quest/QuestAppTimestamp";

    bool m_isQuestGoofy = false;

    bool m_isConnected = false;

    bool m_isTracking = false;
};
