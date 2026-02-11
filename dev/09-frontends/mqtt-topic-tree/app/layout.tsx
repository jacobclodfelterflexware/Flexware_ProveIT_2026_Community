import type { Metadata } from 'next';
import './globals.css';
import AppNavBar from '@/components/AppNavBar';

export const metadata: Metadata = {
  title: 'MQTT Topic Explorer',
  description: 'Real-time MQTT topic tree visualization dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-900">
        <AppNavBar />
        {children}
      </body>
    </html>
  );
}
