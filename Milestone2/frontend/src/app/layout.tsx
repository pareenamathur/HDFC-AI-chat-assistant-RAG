import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'Groww HDFC Assistant',
  description: 'Facts-only HDFC mutual fund assistant — corpus-backed, not investment advice.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body
        className={`${inter.className} min-h-dvh overflow-x-hidden bg-background text-on-surface antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
