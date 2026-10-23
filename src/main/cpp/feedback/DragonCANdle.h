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

#include <string>
#include <vector>

#include <ctre/phoenix6/CANdle.hpp>

#include <wpi/driverstation/DriverStation.hpp>
#include <wpi/hardware/led/AddressableLED.hpp>
#include <wpi/simulation/AddressableLEDSim.hpp>
#include <wpi/system/Timer.hpp>
#include <wpi/util/Color.hpp>

class DragonCANdle
{
public:
	using RGBWColor = ctre::phoenix6::signals::RGBWColor;
	using StripTypeValue = ctre::phoenix6::signals::StripTypeValue;

	enum class AnimationMode
	{
		OFF,
		SOLID,
		ALTERNATING,
		RAINBOW,
		BREATHING,
		BLINKING,
		CHASER,
		CLOSING_IN
	};

	static DragonCANdle *GetInstance();

	void Initialize(int canID, int stripSize, const std::string &canBus = "0", double brightness = 1.0, StripTypeValue type = StripTypeValue::RGB);
	void Periodic();

	// ===== Animation Control =====
	void SetAnimation(AnimationMode mode);
	void SetSolidColor(const wpi::util::Color &color);
	void SetAlternatingColors(const wpi::util::Color &color1, const wpi::util::Color &color2);
	void TurnOff();
	void SetBreathingFrequency(wpi::units::frequency::hertz_t frequency) { m_breathingFrequency = frequency; };
	void SetBlinkingFrequency(wpi::units::frequency::hertz_t frequency) { m_blinkingFrequency = frequency; };

	// ===== Diagnostic Inputs =====
	void SetAlliance(wpi::Alliance alliance) { m_alliance = alliance; };
	void SetQuestStatus(bool connected) { m_questOK = connected; };
	void SetDataLoggerStatus(bool connected) { m_dataLoggerOK = connected; };
	void SetLimelightStatuses(bool ll1) { m_limeLight = ll1; };
	void SetIntakeSensor(bool triggered) { m_intake = triggered; };
	void SetHoodSwitch(bool triggered) { m_hood = triggered; };
	void SetTurretZero(bool triggered) { m_turretZero = triggered; };
	void SetTurretEnd(bool triggered) { m_turretEnd = triggered; };

private:
	DragonCANdle() = default;
	DragonCANdle(const DragonCANdle &) = delete;
	DragonCANdle &operator=(const DragonCANdle &) = delete;

	void UpdateDiagnostics();
	void UpdateAnimation();

	static DragonCANdle *m_instance;

	ctre::phoenix6::hardware::CANdle *m_candle{nullptr};

	// LED Layout
	static constexpr int m_onboardStart = 0;
	static constexpr int m_onboardCount = 8;
	static constexpr int m_externalStart = 17;
	int m_externalCount{0};

	// Diagnostic State
	wpi::Alliance m_alliance{wpi::Alliance::BLUE};
	bool m_questOK{false};
	bool m_dataLoggerOK{false};
	bool m_limeLight{false};
	bool m_intake{false};
	bool m_hood{false};
	bool m_turretZero{false};
	bool m_turretEnd{false};

	wpi::Timer m_diagTimer;

	// Animation State
	AnimationMode m_animMode{AnimationMode::OFF};

	wpi::util::Color m_primaryColor{wpi::util::Color::GREEN};
	wpi::util::Color m_secondaryColor{wpi::util::Color::BLACK};
	double m_brightness{1.0};
	wpi::units::frequency::hertz_t m_blinkingFrequency{0.5_Hz};
	wpi::units::frequency::hertz_t m_breathingFrequency{1_Hz};

	// Alternating pattern state
	int m_alternatingTimer{0};
	static constexpr int m_alternatingPeriod = 10;

	// Limelight diagnostic blinking state
	int m_limelightBlinkTimer{0};
	static constexpr int m_limelightBlinkPeriod = 50; // Frames per limelight display

	// ===== State Caching for Efficiency =====
	// Diagnostic LED state cache (prevents redundant CAN writes)
	wpi::Alliance m_prevAlliance{wpi::Alliance::BLUE};
	bool m_prevQuestOK{false};
	bool m_prevDataLoggerOK{false};
	bool m_prevLimeLight{false};
	bool m_prevIntake{false};
	bool m_prevHood{false};
	bool m_prevTurretZero{false};
	bool m_prevTurretEnd{false};

	// Animation state cache (prevents redundant SetControl calls)
	AnimationMode m_prevAnimMode{AnimationMode::OFF};
	wpi::util::Color m_prevPrimaryColor{wpi::util::Color::GREEN};
	wpi::util::Color m_prevSecondaryColor{wpi::util::Color::BLACK};

	// is this the first run of periodic? Used to force initial LED state setup
	bool m_firstRun{true};
	const int m_attemptsToConfigCandle{5};
};
