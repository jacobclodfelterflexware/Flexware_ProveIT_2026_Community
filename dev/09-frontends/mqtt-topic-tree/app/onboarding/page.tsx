'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type { GeneratedMachineResponse } from '@/types/machines';
import { getMachineByCreator } from '@/lib/machines-api';
import CreateMachineDialog from '@/components/machines/CreateMachineDialog';
import ConnectWizard from '@/components/machines/ConnectWizard';

type OnboardingStep = 'welcome' | 'create' | 'wizard';

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<OnboardingStep>('welcome');
  const [userName, setUserName] = useState('');
  const [nameErrorMessage, setNameErrorMessage] = useState('');
  const [checking, setChecking] = useState(false);

  // Machine creation state
  const [pendingMachine, setPendingMachine] = useState<{
    generated: GeneratedMachineResponse;
    name: string;
    imageBase64?: string;
    autoPilot?: boolean;
    connectMode?: boolean;
  } | null>(null);

  // Particle animation state
  const [particles, setParticles] = useState<Array<{
    id: number;
    x: number;
    y: number;
    size: number;
    speed: number;
    opacity: number;
  }>>([]);

  useEffect(() => {
    const generated = Array.from({ length: 40 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 20 + 10,
      opacity: Math.random() * 0.5 + 0.1,
    }));
    setParticles(generated);
  }, []);

  const handleMachineGenerated = (
    machine: GeneratedMachineResponse,
    name: string,
    imageBase64?: string,
    autoPilot?: boolean,
    connectMode?: boolean
  ) => {
    setPendingMachine({ generated: machine, name, imageBase64, autoPilot, connectMode });
    setStep('wizard');
  };

  const handleWizardComplete = () => {
    router.push(`/machines/${encodeURIComponent(userName.trim())}`);
  };

  const handleBeginJourney = async () => {
    if (!userName.trim()) {
      setNameErrorMessage('Please enter your name to continue');
      return;
    }

    setNameErrorMessage('');
    setChecking(true);

    try {
      await getMachineByCreator(userName.trim());
      // If we get here, a machine exists for this name — it's taken
      setNameErrorMessage('This name is already in use. Please choose a different name.');
    } catch (err) {
      if (err instanceof Error && err.message === 'No machine found for this creator') {
        // 404 — name is available, proceed
        setStep('create');
      } else {
        // API error — don't block onboarding
        setStep('create');
      }
    } finally {
      setChecking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !checking) {
      handleBeginJourney();
    }
  };

  // Welcome / Name Screen
  if (step === 'welcome') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center relative overflow-hidden">
        {/* Animated background particles */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {particles.map((p) => (
            <div
              key={p.id}
              className="absolute rounded-full bg-purple-500"
              style={{
                left: `${p.x}%`,
                top: `${p.y}%`,
                width: `${p.size}px`,
                height: `${p.size}px`,
                opacity: p.opacity,
                animation: `float ${p.speed}s ease-in-out infinite alternate`,
                animationDelay: `${p.id * 0.3}s`,
              }}
            />
          ))}
        </div>

        {/* Radial glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(139,92,246,0.15)_0%,_transparent_70%)]" />

        <div className="relative z-10 text-center max-w-lg mx-auto px-6">
          {/* Logo / Icon */}
          <div className="mb-8 inline-flex items-center justify-center">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shadow-2xl shadow-purple-500/30">
              <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
          </div>

          <h1 className="text-5xl font-bold text-white mb-3 tracking-tight">
            Begin Your Journey
          </h1>
          <p className="text-gray-400 text-lg mb-10">
            Agentic Unified Namespace
          </p>

          <div className="space-y-4 max-w-sm mx-auto">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2 text-left">
                What is your name?
              </label>
              <input
                type="text"
                value={userName}
                onChange={(e) => {
                  setUserName(e.target.value);
                  if (nameErrorMessage) setNameErrorMessage('');
                }}
                onKeyDown={handleKeyDown}
                placeholder="Enter your name..."
                autoFocus
                className={`w-full bg-gray-900/80 backdrop-blur border ${
                  nameErrorMessage ? 'border-red-500' : 'border-gray-600 focus:border-purple-500'
                } rounded-xl px-5 py-3.5 text-gray-100 placeholder-gray-500 focus:outline-none text-lg transition-colors`}
              />
              {nameErrorMessage && (
                <p className="text-red-400 text-sm mt-2 text-left">{nameErrorMessage}</p>
              )}
            </div>

            <button
              onClick={handleBeginJourney}
              disabled={checking}
              className="w-full py-3.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold rounded-xl transition-all text-lg shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {checking ? 'Checking...' : 'Continue'}
            </button>
          </div>
        </div>

        {/* Float animation keyframes */}
        <style jsx>{`
          @keyframes float {
            0% { transform: translateY(0px) translateX(0px); }
            100% { transform: translateY(-30px) translateX(15px); }
          }
        `}</style>
      </div>
    );
  }

  // Machine Creation Dialog (shown inline, full page)
  if (step === 'create') {
    return (
      <div className="min-h-screen bg-gray-950 relative">
        {/* Greeting bar */}
        <div className="bg-gray-900/80 border-b border-gray-800 px-6 py-3">
          <p className="text-gray-400 text-sm">
            Welcome, <span className="text-purple-400 font-medium">{userName}</span>
          </p>
        </div>

        <CreateMachineDialog
          onClose={() => setStep('welcome')}
          onMachineGenerated={handleMachineGenerated}
        />
      </div>
    );
  }

  // Connect Wizard
  if (step === 'wizard' && pendingMachine) {
    return (
      <div className="min-h-screen bg-gray-950 relative">
        {/* Greeting bar */}
        <div className="bg-gray-900/80 border-b border-gray-800 px-6 py-3">
          <p className="text-gray-400 text-sm">
            Welcome, <span className="text-purple-400 font-medium">{userName}</span> — Setting up <span className="text-gray-200 font-medium">{pendingMachine.name}</span>
          </p>
        </div>

        <ConnectWizard
          machine={pendingMachine.generated}
          machineName={pendingMachine.name}
          imageBase64={pendingMachine.imageBase64}
          autoPilotMode={pendingMachine.autoPilot}
          connectMode={pendingMachine.connectMode}
          createdBy={userName.trim()}
          onClose={() => {
            setPendingMachine(null);
            setStep('create');
          }}
          onComplete={handleWizardComplete}
        />
      </div>
    );
  }

  return null;
}
