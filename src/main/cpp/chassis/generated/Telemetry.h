#pragma once

#include "ctre/phoenix6/SignalLogger.hpp"
#include "wpi/nt/NetworkTableInstance.hpp"
#include <wpi/nt/DoubleArrayTopic.hpp>
#include <wpi/nt/DoubleTopic.hpp>
#include <wpi/nt/StringTopic.hpp>
#include <wpi/nt/StructArrayTopic.hpp>
#include <wpi/nt/StructTopic.hpp>
#include <wpi/smartdashboard/Mechanism2d.hpp>
#include <wpi/smartdashboard/MechanismLigament2d.hpp>

#include "chassis/generated/CommandSwerveDrivetrain.h"
#include "utils/logging/signals/DragonDataLoggerMgr.h"

#include "chassis/ChassisConfigMgr.h"
class Telemetry : public DragonDataLogger

{
private:
    wpi::units::meters_per_second_t MaxSpeed = 0_mps; // Maximum speed of the robot, set by chassis configuration manager

    /* Mechanisms to represent the swerve module states */
    std::array<wpi::Mechanism2d, 4> m_moduleMechanisms{
        wpi::Mechanism2d{1, 1},
        wpi::Mechanism2d{1, 1},
        wpi::Mechanism2d{1, 1},
        wpi::Mechanism2d{1, 1},
    };
    /* A direction and length changing ligament for speed representation */
    std::array<wpi::MechanismLigament2d *, 4> m_moduleSpeeds{
        m_moduleMechanisms[0].GetRoot("RootSpeed", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Speed", 0.5, 0_deg),
        m_moduleMechanisms[1].GetRoot("RootSpeed", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Speed", 0.5, 0_deg),
        m_moduleMechanisms[2].GetRoot("RootSpeed", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Speed", 0.5, 0_deg),
        m_moduleMechanisms[3].GetRoot("RootSpeed", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Speed", 0.5, 0_deg),
    };
    /* A direction changing and length constant ligament for module direction */
    std::array<wpi::MechanismLigament2d *, 4> m_moduleDirections{
        m_moduleMechanisms[0].GetRoot("RootDirection", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Direction", 0.1, 0_deg, 0, wpi::util::Color::WHITE),
        m_moduleMechanisms[1].GetRoot("RootDirection", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Direction", 0.1, 0_deg, 0, wpi::util::Color::WHITE),
        m_moduleMechanisms[2].GetRoot("RootDirection", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Direction", 0.1, 0_deg, 0, wpi::util::Color::WHITE),
        m_moduleMechanisms[3].GetRoot("RootDirection", 0.5, 0.5)->Append<wpi::MechanismLigament2d>("Direction", 0.1, 0_deg, 0, wpi::util::Color::WHITE),
    };

    /* Cached state data for periodic logging */
    wpi::math::Pose2d m_cachedPose;
    wpi::math::ChassisVelocities m_cachedSpeeds;
    std::array<wpi::math::SwerveModuleVelocity, 4> m_cachedModuleStates;
    std::array<wpi::math::SwerveModuleVelocity, 4> m_cachedModuleTargets;
    std::array<wpi::math::SwerveModulePosition, 4> m_cachedModulePositions;
    wpi::units::second_t m_cachedOdometryPeriod;

    static constexpr std::string_view m_loggerName = "Swervetelemetry";
    static constexpr std::string_view m_loggingModuleActual = "/Chassis/ModuleActualState";
    static constexpr std::string_view m_loggingModuleTarget = "/Chassis/ModuleTargetState";

    static constexpr std::string_view m_loggingPose2d = "/Chassis/Pose2d";
    static constexpr std::string_view m_loggingChassisVelocities = "/Chassis/ChassisVelocities";
    static constexpr std::string_view m_loggingOdometryPeriod = "/Chassis/OdometryPeriod";
    static constexpr std::string_view m_loggingSeconds = "Seconds";

public:
    /**
     * Construct a telemetry object with the specified max speed of the robot.
     *
     * \param maxSpeed Maximum speed
     */
    Telemetry();

    /** Accept the swerve drive state and telemeterize it to SmartDashboard and SignalLogger. */
    void Telemeterize(subsystems::CommandSwerveDrivetrain::SwerveDriveState const &state);

    /** Periodic data logging implementation */
    void DataLog(uint64_t timestamp) override;
};
