export const metadata = {
  title: "HealthDocs 730",
  description: "Local-first health document intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
