import './globals.css';
import { AuthProvider } from '@/lib/auth';

export const metadata = {
  title: 'Portfolio Tracker — Trading Journal',
  description: 'Modern portfolio tracking and trading journal with analytics, strategy insights, and performance benchmarks.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="id" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
