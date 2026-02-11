'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { GeneratedMachineResponse } from '@/types/machines';
import MachineList from '@/components/machines/MachineList';
import CreateMachineDialog from '@/components/machines/CreateMachineDialog';
import ConnectWizard from '@/components/machines/ConnectWizard';

export default function MachinesPage() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [pendingMachine, setPendingMachine] = useState<{
    generated: GeneratedMachineResponse;
    name: string;
    imageBase64?: string;
    autoPilot?: boolean;
    connectMode?: boolean;
  } | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleMachineGenerated = (machine: GeneratedMachineResponse, name: string, imageBase64?: string, autoPilot?: boolean, connectMode?: boolean) => {
    setPendingMachine({ generated: machine, name, imageBase64, autoPilot, connectMode });
    setShowCreateDialog(false);
  };

  const handleConnectComplete = () => {
    setPendingMachine(null);
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/"
                className="text-gray-400 hover:text-gray-200 flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Dashboard
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-100">Machines</h1>
                <p className="text-sm text-gray-400 mt-1">
                  Onboard and Manage Machines in the Unified Namespace
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowCreateDialog(true)}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Machine
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <MachineList refreshTrigger={refreshTrigger} />
      </main>

      {/* Create Machine Dialog */}
      {showCreateDialog && (
        <CreateMachineDialog
          onClose={() => setShowCreateDialog(false)}
          onMachineGenerated={handleMachineGenerated}
        />
      )}

      {/* Connect Wizard */}
      {pendingMachine && (
        <ConnectWizard
          machine={pendingMachine.generated}
          machineName={pendingMachine.name}
          imageBase64={pendingMachine.imageBase64}
          autoPilotMode={pendingMachine.autoPilot}
          connectMode={pendingMachine.connectMode}
          onClose={() => setPendingMachine(null)}
          onComplete={handleConnectComplete}
        />
      )}
    </div>
  );
}
