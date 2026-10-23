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

#include <span>
#include <string>

#include "feedback/DragonLeds.h"
#include "utils/logging/debug/Logger.h"

DragonLeds::DragonLeds() : m_addressibleLeds()
{
}

DragonLeds *DragonLeds::m_instance = nullptr;
DragonLeds *DragonLeds::GetInstance()
{
    if (m_instance == nullptr)
    {
        m_instance = new DragonLeds();
    }
    return m_instance;
}

void DragonLeds::Initialize(int PWMport, int numLeds)
{
    if (!IsInitialized())
    {
        m_addressibleLeds = new wpi::AddressableLED(PWMport);
        m_addressibleLeds->SetLength(numLeds);

        m_ledBuffer.resize(numLeds);

        SetSolidColor(wpi::util::Color::DARK_GREEN);
        setOn();
    }
    else
    {
        Logger::GetLogger()->LogData(LOGGER_LEVEL::ERROR_ONCE, std::string("DragonLeds"), std::string("Already defined"), std::string("Only one allowed"));
    }
}

bool DragonLeds::IsInitialized() const
{
    return m_addressibleLeds != nullptr;
}

void DragonLeds::setOn()
{
    if (IsInitialized())
    {
        commitLedData();
    }
}

void DragonLeds::setOff()
{
    if (IsInitialized())
    {
        m_ledBuffer = std::vector<wpi::AddressableLED::LEDData>();
        m_addressibleLeds->SetData(m_ledBuffer);
    }
}
void DragonLeds::ResetVariables()
{
    m_loopThroughIndividualLEDs = -1;
    m_colorLoop = 0;
    m_timer = 0;
    m_switchColor = false;
}

void DragonLeds::commitLedData()
{
    if (m_ledBuffer.size() > 0 && IsInitialized())
    {
        m_addressibleLeds->SetData(m_ledBuffer);
    }
}
void DragonLeds::SetSolidColor(wpi::util::Color color)
{
    if (IsInitialized())
    {
        wpi::LEDPattern pattern = wpi::LEDPattern::Solid(color);
        pattern.ApplyTo(m_ledBuffer);
    }
}

void DragonLeds::SetAlternatingColor(wpi::util::Color color1, wpi::util::Color color2)
{
    if (IsInitialized())
    {
        for (unsigned int i = 0; i < m_ledBuffer.size(); i++)
        {
            if (i % 2 == 0)
                m_ledBuffer[i].SetLED(color1);
            else
                m_ledBuffer[i].SetLED(color2);
        }
    }
}

void DragonLeds::SetScorllingRainbow()
{
    if (IsInitialized())
    {
        wpi::units::meter_t kLedSpacing{1 / 120.0};
        wpi::LEDPattern m_rainbow = wpi::LEDPattern::Rainbow(255, 128);
        wpi::LEDPattern m_scrollingRainbow = m_rainbow.ScrollAtAbsoluteVelocity(0.25_mps, kLedSpacing);
        m_scrollingRainbow.ApplyTo(m_ledBuffer);
    }
}

void DragonLeds::SetSpecificLED(int id, wpi::util::Color color)
{
    if (IsInitialized())
    {
        m_ledBuffer[id].SetLED(color);
    }
}

void DragonLeds::SetBufferAllLEDsBlack()
{
    if (IsInitialized())
    {
        wpi::LEDPattern pattern = wpi::LEDPattern::Solid(wpi::util::Color::BLACK);
        pattern.ApplyTo(m_ledBuffer);
    }
}

void DragonLeds::SetBufferAllLEDsColorBrightness(wpi::util::Color color, double brightness)
{
    if (IsInitialized())
    {
        wpi::LEDPattern base = wpi::LEDPattern::Solid(color);
        wpi::LEDPattern pattern = base.AtBrightness(brightness);

        pattern.ApplyTo(m_ledBuffer);
    }
}
void DragonLeds::SetBreathingPattern(wpi::util::Color color, wpi::units::time::second_t period)
{
    if (IsInitialized())
    {

        wpi::LEDPattern base = wpi::LEDPattern::Solid(color);
        wpi::LEDPattern pattern = base.Breathe(period);

        pattern.ApplyTo(m_ledBuffer);
    }
}

void DragonLeds::SetBlinkingPattern(wpi::util::Color color, wpi::units::time::second_t cycleTime)
{
    if (IsInitialized())
    {
        wpi::LEDPattern base = wpi::LEDPattern::Solid(color);
        wpi::LEDPattern pattern = base.Blink(cycleTime);

        pattern.ApplyTo(m_ledBuffer);
    }
}

void DragonLeds::SetAlternatingColorBlinkingPattern(wpi::util::Color color1, wpi::util::Color color2)
{
    if (IsInitialized())
    {
        if (m_ledBuffer.size() > 0)
        {
            if (m_timer > 2 * m_blinkPatternPeriod)
                m_timer = 0;

            int blinkState = (m_timer / m_blinkPatternPeriod) % 2;

            if (blinkState == 0)
                SetAlternatingColor(color1, color2);
            else
                SetAlternatingColor(color2, color1);

            m_timer++;
        }
    }
}

void DragonLeds::SetChaserPattern(wpi::util::Color color)
{
    if (IsInitialized())
    {
        if (m_ledBuffer.size() > 0)
        {
            m_loopThroughIndividualLEDs += m_loopThroughIndividualLEDs < static_cast<int>(m_ledBuffer.size()) - 1 ? 1 : -m_loopThroughIndividualLEDs;
            if (!m_switchColor)
            {
                m_lastColor = m_lastColor == color ? wpi::util::Color::BLACK : color;
            }
            m_switchColor = m_loopThroughIndividualLEDs != static_cast<int>(m_ledBuffer.size()) - 1;

            SetSpecificLED(m_loopThroughIndividualLEDs, m_lastColor);
        }
    }
}

void DragonLeds::SetClosingInChaserPattern(wpi::util::Color inputColor)
{
    if (IsInitialized())
    {
        if (m_ledBuffer.size() > 0)
        {
            if (m_timer == 7)
            {
                int halfLength = (m_ledBuffer.size() - 1) / 2;
                m_loopThroughIndividualLEDs += m_loopThroughIndividualLEDs < halfLength ? 1 : -m_loopThroughIndividualLEDs;
                int loopout = (m_ledBuffer.size() - 1) - m_loopThroughIndividualLEDs;
                auto color = m_colorLoop >= 0 ? inputColor : wpi::util::Color::BLACK;
                m_colorLoop += m_colorLoop < halfLength ? 1 : -((m_colorLoop * 2) + 1);
                SetSpecificLED(m_loopThroughIndividualLEDs, color);
                SetSpecificLED(loopout, color);

                m_timer = 0;
            }
            m_timer++;
        }
    }
}

void DragonLeds::DiagnosticPattern(wpi::Alliance alliance, bool questStatus, bool dataLoggerStatus, bool ll1Status, bool ll2Status, bool ll3Status,
                                   bool intakeSensor, bool hoodSwitch, bool turretZero, bool turretEnd)
{
    if (IsInitialized())
    {
        auto allianceColor = alliance == wpi::Alliance::BLUE ? wpi::util::Color::BLUE : wpi::util::Color::RED;
        SetSpecificLED(m_allianceColorLED, allianceColor);

        auto questStatusColor = questStatus ? wpi::util::Color::GREEN : wpi::util::Color::DARK_RED;
        SetSpecificLED(m_questLED, questStatusColor);

        auto ll1StatusColor = ll1Status ? wpi::util::Color::GREEN : wpi::util::Color::DARK_RED;
        SetSpecificLED(m_limeLight1LED, ll1StatusColor);

        auto ll2StatusColor = ll2Status ? wpi::util::Color::GREEN : wpi::util::Color::DARK_RED;
        SetSpecificLED(m_limeLight2LED, ll2StatusColor);

        auto ll3StatusColor = ll3Status ? wpi::util::Color::GREEN : wpi::util::Color::DARK_RED;
        SetSpecificLED(m_limeLight3LED, ll3StatusColor);

        auto dataLoggerStatusColor = dataLoggerStatus ? wpi::util::Color::GREEN : wpi::util::Color::DARK_RED;
        SetSpecificLED(m_dataLoggerLED, dataLoggerStatusColor);

        auto intakeStatusColor = intakeSensor ? wpi::util::Color::YELLOW : wpi::util::Color::BLACK;
        SetSpecificLED(m_intakeSensorLED, intakeStatusColor);

        auto hoodStatusColor = hoodSwitch ? wpi::util::Color::YELLOW : wpi::util::Color::BLACK;
        SetSpecificLED(m_hoodSwitchLED, hoodStatusColor);

        auto turretZeroStatusColor = turretZero ? wpi::util::Color::YELLOW : wpi::util::Color::BLACK;
        SetSpecificLED(m_turretZeroLED, turretZeroStatusColor);

        auto turretEndStatusColor = turretEnd ? wpi::util::Color::YELLOW : wpi::util::Color::BLACK;
        SetSpecificLED(m_turretEndLED, turretEndStatusColor);
    }
}