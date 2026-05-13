import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-geist-sans',
})

export const metadata: Metadata = {
  title: 'HDFC Mutual Fund Assistant',
  description: 'Factual information about HDFC mutual funds — not investment advice.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} min-h-screen bg-hdfc-bg text-gray-100`}>
        {children}
      </body>
    </html>
  )
}
