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

// C++ Includes
#include <string>

// FRC includes
#include "wpi/smartdashboard/SendableChooser.hpp"
#include "wpi/system/Timer.hpp"

/// @class DragonTimedClass
/// @brief Base class that instruments a derived class' periodic work so its execution time and the
///        activity it is currently performing can be logged for performance analysis.
///
/// Any class that wants per-loop timing simply inherits from @c DragonTimedClass and passes its
/// name to the constructor. Around the work it wants to measure it calls @c StartPeriodicTiming()
/// and @c EndPeriodicTiming() (or uses the RAII @c ScopedTimer). It may also call
/// @c SetCurrentActivity() to record what the code is doing this loop (e.g. the active command or
/// state name).
///
/// The feature is turned on from the dashboard. A single global @c SendableChooser lets the driver
/// team pick where timing data goes:
///   - @c OFF           : no timing overhead is logged (default).
///   - @c NETWORK_TABLE : timing + activity are published over NetworkTables.
///   - @c DATA_FILE     : reserved hook for on-robot data-file logging (currently disabled).
///
/// @note The dashboard chooser is shared by every derived instance. Call
///       @c PutTimingSelectionOnDashboard() once at startup and @c UpdateTimingSelection() from a
///       periodic loop so the selection can be changed at runtime.
class DragonTimedClass
{
public:
    /// @enum TimingLogOption
    /// @brief Where the collected timing/activity data should be sent.
    enum class TimingLogOption
    {
        OFF,           ///< Timing collection disabled (no logging performed).
        NETWORK_TABLE, ///< Publish timing/activity over NetworkTables.
        DATA_FILE      ///< Reserved for data-file logging (hook only - data logging is off today).
    };

    /// @brief Construct the timed class.
    /// @param [in] className Name used to group this class' timing data (network table / file key).
    explicit DragonTimedClass(const std::string &className);

    virtual ~DragonTimedClass() = default;

    /// @brief Publish the timing-destination chooser to the dashboard. Call once at startup.
    static void PutTimingSelectionOnDashboard();

    /// @brief Read the timing-destination selection from the dashboard. Throttled internally so it
    ///        is safe to call every loop.
    static void UpdateTimingSelection();

    /// @brief Get the currently selected timing destination.
    /// @return TimingLogOption current selection.
    static TimingLogOption GetTimingOption() { return s_option; }

    /// @class ScopedTimer
    /// @brief RAII helper that times a scope. Starts timing on construction and ends it on
    ///        destruction, so a derived class can simply write:
    ///        @code
    ///        void MyClass::Periodic()
    ///        {
    ///            DragonTimedClass::ScopedTimer timer(*this, "Periodic", "my activity");
    ///            // ... work ...
    ///        }
    ///        @endcode
    class ScopedTimer
    {
    public:
        /// @brief Start timing the enclosing scope.
        /// @param [in] owner    The DragonTimedClass being timed.
        /// @param [in] label    Name of the timed section (e.g. "Periodic", "Initialize", "Execute").
        ///                      Used as the network-table key so different sections don't overwrite
        ///                      each other.
        /// @param [in] activity Optional description of what the code is doing this loop.
        ScopedTimer(DragonTimedClass &owner, const std::string &label, const std::string &activity = "");
        ~ScopedTimer();

    private:
        DragonTimedClass &m_owner;
    };

protected:
    /// @brief Mark the start of a timed section.
    /// @param [in] label    Name of the timed section (e.g. "Periodic", "Initialize", "Execute").
    /// @param [in] activity Optional description of what the code is doing this loop.
    void StartTiming(const std::string &label, const std::string &activity = "");

    /// @brief Mark the end of the timed section and log the elapsed time (if enabled).
    void EndTiming();

    /// @brief Get the last measured duration in milliseconds.
    /// @return double elapsed milliseconds from the most recent Start/End pair.
    double GetLastElapsedMs() const { return m_lastElapsedMs; }

private:
    /// @brief Log the elapsed time and current activity to the selected destination.
    /// @param [in] elapsedMs measured duration in milliseconds.
    void LogTiming(double elapsedMs) const;

    /// @brief Hook for future on-robot data-file logging. Data logging is currently disabled, so
    ///        this is intentionally a stub - implement it when the data logger is brought online.
    /// @param [in] elapsedMs measured duration in milliseconds.
    void LogTimingToDataFile(double elapsedMs) const;

    std::string m_className;       ///< Grouping name for this class' timing data.
    std::string m_currentLabel;    ///< Name of the section currently being timed.
    std::string m_currentActivity; ///< What the code is doing this loop.
    wpi::Timer m_timer;            ///< Times the section.
    double m_lastElapsedMs;        ///< Most recent measured duration (ms).

    static TimingLogOption s_option;                        ///< Shared selection for all timed classes.
    static wpi::SendableChooser<TimingLogOption> s_chooser; ///< Dashboard chooser.
    static int s_cyclingCounter;                            ///< Throttles dashboard reads.
};
