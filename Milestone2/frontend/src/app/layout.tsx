import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'HDFC Assistant',
  description: 'Facts-only HDFC mutual fund assistant — corpus-backed, not investment advice.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark h-full ${inter.variable}`}>
      <body
        className={`${inter.className} h-dvh max-h-dvh overflow-hidden bg-background text-text-primary antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
