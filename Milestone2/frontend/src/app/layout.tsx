import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'HDFC Mutual Fund Assistant',
  description: 'AI-powered assistant for HDFC mutual fund information',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        {children}
      </body>
    </html>
  )
}
