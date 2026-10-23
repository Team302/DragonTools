#include "chassis/generated/Telemetry.h"
#include "utils/logging/debug/Logger.h"
#include <wpi/smartdashboard/SmartDashboard.hpp>

using namespace ctre::phoenix6;

Telemetry::Telemetry()
{
    /* Set up the module state Mechanism2d telemetry */
    for (size_t i = 0; i < m_moduleSpeeds.size(); ++i)
    {
        wpi::SmartDashboard::PutData("Module " + std::to_string(i), &m_moduleMechanisms[i]);
    }
}

void Telemetry::Telemeterize(subsystems::CommandSwerveDrivetrain::SwerveDriveState const &state)
{
    auto Logger = Logger::GetLogger();
    ChassisConfigMgr *configMgr = ChassisConfigMgr::GetInstance();
    MaxSpeed = configMgr->GetMaxSpeed();

    // Cache state data for periodic logging
    m_cachedPose = state.Pose;
    m_cachedSpeeds = state.Velocity;
    for (size_t i = 0; i < state.ModuleVelocities.size(); ++i)
    {
        m_cachedModuleStates[i] = state.ModuleVelocities[i];
    }
    for (size_t i = 0; i < state.ModuleTargets.size(); ++i)
    {
        m_cachedModuleTargets[i] = state.ModuleTargets[i];
    }
    for (size_t i = 0; i < state.ModulePositions.size(); ++i)
    {
        m_cachedModulePositions[i] = state.ModulePositions[i];
    }
    m_cachedOdometryPeriod = state.OdometryPeriod;

    /* Telemeterize each module state to a Mechanism2d */
    for (size_t i = 0; i < m_moduleSpeeds.size(); ++i)
    {
        m_moduleDirections[i]->SetAngle(state.ModuleVelocities[i].angle.Degrees());
        m_moduleSpeeds[i]->SetAngle(state.ModuleVelocities[i].angle.Degrees());
        m_moduleSpeeds[i]->SetLength(state.ModuleVelocities[i].velocity / (2 * MaxSpeed));
    }

    double x = m_cachedPose.X().value();
    double y = m_cachedPose.Y().value();
    double rot = m_cachedPose.Rotation().Radians().value();
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("Pose2dX"), x);
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("Pose2dY"), y);
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("Pose2dRotation"), rot);
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontLeftActualStateSpeed"), m_cachedModuleStates[0].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontLeftActualStateAngle"), m_cachedModuleStates[0].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontRightActualStateSpeed"), m_cachedModuleStates[1].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontRightActualStateAngle"), m_cachedModuleStates[1].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackLeftActualStateSpeed"), m_cachedModuleStates[2].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackLeftActualStateAngle"), m_cachedModuleStates[2].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackRightActualStateSpeed"), m_cachedModuleStates[3].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackRightActualStateAngle"), m_cachedModuleStates[3].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontLeftTargetStateSpeed"), m_cachedModuleTargets[0].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontLeftTargetStateAngle"), m_cachedModuleTargets[0].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontRightTargetStateSpeed"), m_cachedModuleTargets[1].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("FrontRightTargetStateAngle"), m_cachedModuleTargets[1].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackLeftTargetStateSpeed"), m_cachedModuleTargets[2].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackLeftTargetStateAngle"), m_cachedModuleTargets[2].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackRightTargetStateSpeed"), m_cachedModuleTargets[3].velocity.value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("BackRightTargetStateAngle"), m_cachedModuleTargets[3].angle.Degrees().value());
    Logger->LogData(LOGGER_LEVEL::PRINT, std::string("SwerveTelemetry"), std::string("OdometryPeriod"), m_cachedOdometryPeriod.value());
}

void Telemetry::DataLog(uint64_t timestamp)
{

    LogPose2dData(timestamp, m_loggingPose2d, m_cachedPose);

    LogChassisSpeedsData(timestamp, m_loggingChassisVelocities, m_cachedSpeeds);

    // Log module states
    LogSwerveModuleStateData(timestamp, m_loggingModuleActual, m_cachedModuleStates);

    // Log module targets
    LogSwerveModuleStateData(timestamp, m_loggingModuleTarget, m_cachedModuleTargets);
    // OdometryPeriod logged as a double
    LogDoubleData(timestamp, m_loggingOdometryPeriod, m_cachedOdometryPeriod.value(), m_loggingSeconds);
}
