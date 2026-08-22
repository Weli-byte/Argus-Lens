import type { Metadata, Viewport } from "next";
import {
  Bricolage_Grotesque,
  Instrument_Sans,
  Instrument_Serif,
  Martian_Mono,
} from "next/font/google";
import "./globals.css";
import Providers from "./providers";

/* Yön A "Optik Enstrüman" — aşırı ağırlık kontrastı için 200 ve 800 birlikte.
   latin-ext Türkçe ş/ğ/ı/İ karakterleri için ZORUNLU. */
const display = Bricolage_Grotesque({
  subsets: ["latin", "latin-ext"],
  weight: ["200", "800"],
  variable: "--font-bricolage",
  display: "swap",
});

const sans = Instrument_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400"],
  variable: "--font-instrument-sans",
  display: "swap",
});

/* Tek manifesto satırı için — ilk ekranda değil, preload kapalı. */
const serif = Instrument_Serif({
  subsets: ["latin", "latin-ext"],
  weight: "400",
  style: "italic",
  variable: "--font-instrument-serif",
  display: "swap",
  preload: false,
});

/* Ölçüm katmanı: FPS, güven %, vital. */
const mono = Martian_Mono({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400"],
  variable: "--font-martian-mono",
  display: "swap",
  // Preload kapalı: hero posteri (LCP adayı) ile bant genişliği yarışıyordu.
  // Küçük kadran/ölçüm etiketlerinde swap görsel olarak zararsız.
  preload: false,
});

export const metadata: Metadata = {
  title: "ArgusLens — Biyonik Lens Görü Platformu",
  description:
    "Göz artık bir arayüz. Gerçek zamanlı nesne tespiti, vital izleme ve klinik AI yorumlama tek optik hat üzerinde.",
};

export const viewport: Viewport = {
  themeColor: "#0d1512",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="tr"
      data-theme="dark"
      className={`${display.variable} ${sans.variable} ${serif.variable} ${mono.variable} h-full`}
    >
      <body className="h-full antialiased font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
