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
#include "wpi/commands2/Command.hpp"
#include "wpi/commands2/CommandHelper.hpp"

// Team 302 includes
#include "utils/logging/timing/DragonTimedClass.h"

class BaseMechSubsystem;

/// @class DragonTimedCommand
/// @brief Command base class that automatically times a command's @c Initialize() and @c Execute()
///        work and logs it inside the owning mechanism's table.
///
/// This uses the non-virtual-interface (template method) pattern so timing is completely automatic:
/// the scheduler calls the @c final @c Initialize() / @c Execute() defined here, which wrap a timer
/// around the protected @c Init() / @c Run() hooks. Derived commands override those hooks instead of
/// @c Initialize() / @c Execute() and never call any timing code themselves.
/// (The hooks are named @c Init() / @c Run() because a wrapper method cannot share the name of the
/// method it wraps; @c Initialize() / @c Execute() are dispatched by the scheduler to this base.)
///
/// The timing group is the owning mechanism's network-table name, so a command's timing appears
/// alongside the mechanism's other data, e.g. @c "Launcher/LauncherIdle Initialize (ms)".
///
/// @note Timing only happens when enabled from the dashboard (see @c DragonTimedClass); when off,
///       the hooks are still called but no timing/logging overhead is incurred.
class DragonTimedCommand : public wpi::cmd::Command, public DragonTimedClass
{
public:
    /// @brief Construct the timed command.
    /// @param [in] mechanism The mechanism this command runs on; its network-table name is used as
    ///                        the timing group so timing stays within that subsystem's table.
    explicit DragonTimedCommand(BaseMechSubsystem *mechanism);

    ~DragonTimedCommand() override = default;

    /// @brief Scheduler entry point for command start. Times and forwards to @c Init().
    ///        Marked @c final so derived commands cannot bypass timing.
    void Initialize() final;

    /// @brief Scheduler entry point for the per-loop command body. Times and forwards to
    ///        @c Run(). Marked @c final so derived commands cannot bypass timing.
    void Execute() final;

    /// @brief Scheduler entry point for command end. Times and forwards to @c Exit().
    ///        Marked @c final so derived commands cannot bypass timing.
    void End(bool interrupted) final;

    /// @brief Scheduler entry point for command completion check. Times and forwards to @c IsDone().
    ///        Marked @c final so derived commands cannot bypass timing.
    bool IsFinished() final;

protected:
    /// @brief Override this instead of @c Initialize(). Runs once when the command is scheduled;
    ///        timed automatically.
    virtual void Init() {}

    /// @brief Override this instead of @c Execute(). Runs every loop while the command is active;
    ///        timed automatically.
    virtual void Run() {}

    /// @brief Override this instead of @c End(). Runs when the command is ended;
    ///        timed automatically.
    virtual void Exit(bool interrupted) {}

    /// @brief Override this to indicate when the command is finished. Runs every loop while the command is active.
    ///        timed automatically.
    virtual bool IsDone() { return false; }
};
