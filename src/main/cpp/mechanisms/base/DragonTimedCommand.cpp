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

// Team 302 includes
#include "mechanisms/base/DragonTimedCommand.h"
#include "mechanisms/base/BaseMechSubsystem.h"

DragonTimedCommand::DragonTimedCommand(BaseMechSubsystem *mechanism)
    : wpi::cmd::Command(), DragonTimedClass(mechanism->GetNetworkTableName())
{
}

void DragonTimedCommand::Initialize()
{
    // GetName() (set via Command::SetName in the derived constructor) is used so each command's
    // timing gets a distinct key within the mechanism's table, e.g. "LauncherIdle Initialize (ms)".
    DragonTimedClass::ScopedTimer timer(*this, GetName() + " Initialize");
    Init();
}

void DragonTimedCommand::Execute()
{
    DragonTimedClass::ScopedTimer timer(*this, GetName() + " Execute");
    Run();
}

void DragonTimedCommand::End(bool interrupted)
{
    DragonTimedClass::ScopedTimer timer(*this, GetName() + " End");
    Exit(interrupted);
}

bool DragonTimedCommand::IsFinished()
{
    DragonTimedClass::ScopedTimer timer(*this, GetName() + " IsFinished");
    return IsDone();
}