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

#include "wpi/hardware/led/LEDPattern.hpp"
#include <array>
#include <vector>
#include <wpi/hardware/led/AddressableLED.hpp>

#include <utils/FMSData.h>

class DragonLeds
{
public:
	std::vector<wpi::AddressableLED::LEDData> m_ledBuffer;

	void Initialize(int PWMport, int numLeds);
	bool IsInitialized() const;

	void commitLedData();

	void setOn();
	void setOff();
	void ResetVariables();

	void SetSolidColor(wpi::util::Color color);
	void SetAlternatingColor(wpi::util::Color color1, wpi::util::Color color2);
	void SetBufferAllLEDsBlack();
	void SetScorllingRainbow();
	void SetSpecificLED(int id, wpi::util::Color color);
	void SetBufferAllLEDsColorBrightness(wpi::util::Color color, double brightness);
	void SetBreathingPattern(wpi::util::Color color, wpi::units::time::second_t period);
	void SetBlinkingPattern(wpi::util::Color color, wpi::units::time::second_t cycleTime);
	void SetAlternatingColorBlinkingPattern(wpi::util::Color color1, wpi::util::Color color2);
	void SetChaserPattern(wpi::util::Color color);
	void SetClosingInChaserPattern(wpi::util::Color inputColor);

	void DiagnosticPattern(wpi::Alliance alliance, bool questStatus, bool dataLoggerStatus, bool ll1Status, bool ll2Status, bool ll3Status,
						   bool intakeSensor, bool hoodSwitch, bool turretZero, bool turretEnd);

	static DragonLeds *GetInstance();

private:
	static DragonLeds *m_instance;
	wpi::AddressableLED *m_addressibleLeds;
	int m_numberofDiagnosticLEDs = 9;

	int m_loopThroughIndividualLEDs = -1;
	int m_colorLoop = 0;
	int m_timer = 0;
	bool m_switchColor = false;
	wpi::util::Color m_lastColor = wpi::util::Color::BLACK;

	const int m_blinkPatternPeriod = 10;
	const int m_allianceColorLED = 0;
	const int m_questLED = 1;
	const int m_limeLight1LED = 2;
	const int m_limeLight2LED = 3;
	const int m_limeLight3LED = 4;
	const int m_dataLoggerLED = 5;
	const int m_intakeSensorLED = 6;
	const int m_hoodSwitchLED = 7;
	const int m_turretZeroLED = 8;
	const int m_turretEndLED = 9;

	DragonLeds();
};
