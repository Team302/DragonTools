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

// FRC includes
#include <wpi/smartdashboard/SmartDashboard.hpp>

// Team 302 includes
#include "utils/logging/debug/Logger.h"
#include "utils/logging/timing/DragonTimedClass.h"
#include "wpi/system/Timer.hpp"

// static member definitions
DragonTimedClass::TimingLogOption DragonTimedClass::s_option = DragonTimedClass::TimingLogOption::OFF;
wpi::SendableChooser<DragonTimedClass::TimingLogOption> DragonTimedClass::s_chooser;
int DragonTimedClass::s_cyclingCounter = 0;

/// @brief Construct the timed class.
DragonTimedClass::DragonTimedClass(const std::string &className) : m_className(className),
                                                                   m_currentLabel(""),
                                                                   m_currentActivity(""),
                                                                   m_timer(),
                                                                   m_lastElapsedMs(0.0)
{
}

/// @brief Publish the timing-destination chooser to the dashboard. Call once at startup.
void DragonTimedClass::PutTimingSelectionOnDashboard()
{
    s_chooser.SetDefaultOption("OFF", TimingLogOption::OFF);
    s_chooser.AddOption("NETWORK_TABLE", TimingLogOption::NETWORK_TABLE);
    s_chooser.AddOption("DATA_FILE", TimingLogOption::DATA_FILE);
    wpi::SmartDashboard::PutData("Timing Logging", &s_chooser);

    s_cyclingCounter = 0;
}

/// @brief Read the timing-destination selection from the dashboard (throttled).
void DragonTimedClass::UpdateTimingSelection()
{
    s_cyclingCounter += 1;      // count 20ms loops
    if (s_cyclingCounter >= 25) // execute every 500ms
    {
        s_cyclingCounter = 0;
        s_option = s_chooser.GetSelected();
    }
}

/// @brief Mark the start of a timed section.
void DragonTimedClass::StartTiming(const std::string &label, const std::string &activity)
{
    if (s_option == TimingLogOption::OFF)
    {
        return;
    }
    m_currentLabel = label;
    m_currentActivity = activity;
    m_timer.Restart();
}

/// @brief Mark the end of the timed section and log the elapsed time (if enabled).
void DragonTimedClass::EndTiming()
{
    if (s_option == TimingLogOption::OFF)
    {
        return;
    }

    m_lastElapsedMs = wpi::units::millisecond_t(m_timer.Get()).value();
    m_timer.Stop();

    LogTiming(m_lastElapsedMs);
}

/// @brief Log the elapsed time and current activity to the selected destination.
void DragonTimedClass::LogTiming(double elapsedMs) const
{
    switch (s_option)
    {
    case TimingLogOption::NETWORK_TABLE:
    {
        // LogDataDirectlyOverNT publishes regardless of the debug Logger option, so timing can be
        // enabled independently of the rest of the logging framework.
        const std::string group = "Timing/" + m_className;
        Logger::GetLogger()->LogDataDirectlyOverNT(group, m_currentLabel + " (ms)", elapsedMs);
        if (!m_currentActivity.empty())
        {
            Logger::GetLogger()->LogDataDirectlyOverNT(group, m_currentLabel + " activity", m_currentActivity);
        }
    }
    break;

    case TimingLogOption::DATA_FILE:
        LogTimingToDataFile(elapsedMs);
        break;

    default: // TimingLogOption::OFF
        break;
    }
}

/// @brief Hook for future on-robot data-file logging.
void DragonTimedClass::LogTimingToDataFile(double elapsedMs) const
{
    // SystemCore TO DO: data-file logging is currently disabled. When the data logger is brought
    // online, record m_className, m_currentActivity, and elapsedMs here (see DragonDataLoggerMgr).
    (void)elapsedMs; // avoid unused parameter warning
}

/// @brief Start timing the enclosing scope.
DragonTimedClass::ScopedTimer::ScopedTimer(DragonTimedClass &owner, const std::string &label, const std::string &activity) : m_owner(owner)
{
    m_owner.StartTiming(label, activity);
}

DragonTimedClass::ScopedTimer::~ScopedTimer()
{
    m_owner.EndTiming();
}
