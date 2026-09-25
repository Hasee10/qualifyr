import { ImageResponse } from "next/og"

export const runtime = "edge"
export const alt = "Qualifyr — see who actually buys"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

/** Code-generated OG image, not a static asset - so it never goes stale when the copy
 *  changes and needs no design tool to produce. */
export default async function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #0a0a0a 0%, #171717 100%)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              display: "flex",
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "#ffffff",
            }}
          />
          <span style={{ fontSize: 32, fontWeight: 600 }}>Qualifyr</span>
        </div>
        <div style={{ display: "flex", marginTop: 48, fontSize: 60, fontWeight: 600, lineHeight: 1.15, maxWidth: 900 }}>
          See who actually{" "}
          <span style={{ color: "#ffffff", textDecoration: "underline", marginLeft: 16 }}>buys</span>
        </div>
        <div style={{ display: "flex", marginTop: 24, fontSize: 26, color: "#a3a3a3", maxWidth: 820 }}>
          Buyer-only B2B lead discovery, qualification and outreach for Pakistan &amp; the GCC.
        </div>
      </div>
    ),
    { ...size }
  )
}
