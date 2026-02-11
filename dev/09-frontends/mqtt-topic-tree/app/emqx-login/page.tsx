'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

function EMQXLoginContent() {
  const searchParams = useSearchParams();
  const broker = searchParams.get('broker') || 'uncurated';
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);

  const emqxUrl = broker === 'curated'
    ? (process.env.NEXT_PUBLIC_EMQX_CURATED_URL || 'http://YOUR_HOSTNAME:31084')
    : (process.env.NEXT_PUBLIC_EMQX_DASHBOARD_URL || 'http://YOUR_HOSTNAME:31083');

  useEffect(() => {
    async function autoLogin() {
      try {
        // Get token from our API
        const response = await fetch(`/api/emqx/token?broker=${broker}`);
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.error || 'Failed to get token');
        }

        const { token } = await response.json();

        // We can't directly set localStorage on a different origin
        // Instead, redirect to EMQX with token in URL hash (EMQX may support this)
        // Or show success and let user know they need to login once

        setStatus('success');

        // Redirect to EMQX dashboard after brief delay
        setTimeout(() => {
          window.location.href = emqxUrl;
        }, 500);

      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setStatus('error');
      }
    }

    autoLogin();
  }, [broker, emqxUrl]);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 max-w-md w-full text-center">
      {status === 'loading' && (
        <>
          <div className="w-12 h-12 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-100 mb-2">Connecting to EMQX</h2>
          <p className="text-gray-400">Authenticating...</p>
        </>
      )}

      {status === 'success' && (
        <>
          <div className="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-100 mb-2">Redirecting to EMQX</h2>
          <p className="text-gray-400">Opening dashboard...</p>
        </>
      )}

      {status === 'error' && (
        <>
          <div className="w-12 h-12 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-100 mb-2">Connection Failed</h2>
          <p className="text-red-400 mb-4">{error}</p>
          <a
            href={emqxUrl}
            className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
          >
            Open EMQX Manually
          </a>
        </>
      )}
    </div>
  );
}

export default function EMQXLoginPage() {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <Suspense fallback={
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 max-w-md w-full text-center">
          <div className="w-12 h-12 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-100 mb-2">Loading...</h2>
        </div>
      }>
        <EMQXLoginContent />
      </Suspense>
    </div>
  );
}
