import Atmosphere from "@/components/landing/Atmosphere";
import SiteNav from "@/components/landing/SiteNav";
import Hero from "@/components/landing/Hero";
import SceneBlock from "@/components/landing/SceneBlock";
import SpecSheet from "@/components/landing/SpecSheet";
import ClosingCTA from "@/components/landing/ClosingCTA";
import SiteFooter from "@/components/landing/SiteFooter";
import SceneChoreography from "@/components/landing/SceneChoreography";
import FocusReticle from "@/components/landing/FocusReticle";

export default function LandingPage() {
  return (
    <>
      <a href="#anlati" className="skip-link btn btn-primary">
        İçeriğe geç
      </a>

      <Atmosphere />
      <SiteNav />
      <FocusReticle />
      <SceneChoreography />

      <main>
        <Hero />

        {/* Manifesto — tek serif italik satır. Sayfada bir kez kullanılır. */}
        <section className="section">
          <div className="shell grid grid-cols-12">
            <p
              className="t-manifesto col-span-12 border-t border-[var(--edge-rule)]
                         pt-[var(--p-space-5)] md:col-span-8 md:col-start-4"
              data-reveal
            >
              Bir mercek ışığı yalnızca taşımaz; hangi ışığın önemli olduğuna
              karar verir. ArgusLens bu kararı kareyi bırakmadan verir.
            </p>
          </div>
        </section>

        <div id="anlati">
          <SceneBlock
            index="02"
            kicker="Tarama"
            title={
              <>
                SANİYEDE <span className="t-counter">altmış</span> KARE
              </>
            }
            body="Lens sensörü ham kareyi doğrudan çıkarım hattına verir. Kuyruk
                  derinliği eşiği aştığında kare atlanır, gecikme büyümez —
                  bir sonraki kare her zaman taze gelir."
            video="02-scan"
            videoAlt="Biyonik lensin optik hattı; sensörden çıkarım katmanına geçen kare akışı"
            hudLabel="KAM 02 · HAT"
            readouts={[
              { label: "Kare hızı", value: "60 FPS" },
              { label: "Çıkarım", value: "24 MS" },
              { label: "Kuyruk derinliği", value: "3 / 32" },
            ]}
          />

          <SceneBlock
            index="03"
            kicker="Tespit"
            title={
              <>
                HER NESNE, <span className="t-counter">güven oranıyla</span>
              </>
            }
            body="GroundingDINO sıfır-atış çalışır: modele önceden öğretilmemiş
                  nesneleri de metinle sorarsınız. Her kutu bir olasılıkla gelir;
                  eşiğin altındakiler operatöre hiç gösterilmez."
            video="03-detect"
            videoAlt="Sahnedeki nesnelerin üzerinde beliren tespit kutuları ve güven oranları"
            hudLabel="KAM 03 · TESPİT"
            readouts={[
              { label: "Araç", value: "%94" },
              { label: "İnsan", value: "%97" },
              { label: "Eşik altı", value: "GİZLİ" },
            ]}
            flip
          />

          <SceneBlock
            index="04"
            kicker="Yorum"
            title={
              <>
                HAM PİKSEL DEĞİL, <span className="t-counter">klinik okuma</span>
              </>
            }
            body="Temporal Transformer 90 saniyelik pencereyi izler; nabız, SpO₂
                  ve göz içi basıncını kare akışıyla birlikte değerlendirir.
                  Çıktı bir sayı değil, bir cümledir."
            video="04-read"
            videoAlt="Gözden alınan verilerin vital göstergelere ve klinik yoruma dönüşmesi"
            hudLabel="KAM 04 · VITAL"
            readouts={[
              { label: "Nabız", value: "74 BPM" },
              { label: "SpO₂", value: "%98.2" },
              { label: "Ufuk", value: "90 SN" },
            ]}
          />

          <SceneBlock
            index="05"
            kicker="Aksiyon"
            title={
              <>
                EŞİK AŞILDIĞINDA <span className="t-counter">saniyeler</span>
              </>
            }
            body="Anomali skoru σ > 2.4 sınırını geçtiğinde uyarı operatöre,
                  kayıt arşive, olay zaman çizelgesine aynı anda düşer.
                  Kimse ekrana bakmayı beklemez."
            video="05-act"
            videoAlt="Anomali eşiği aşıldığında tetiklenen uyarı ve operatör devri"
            hudLabel="KAM 05 · UYARI"
            readouts={[
              { label: "Anomali skoru", value: "σ 2.9" },
              { label: "Uyarı gecikmesi", value: "180 MS" },
              { label: "Arşiv", value: "YAZILDI" },
            ]}
            flip
          />
        </div>

        <SpecSheet />
        <ClosingCTA />
      </main>

      <SiteFooter />
    </>
  );
}
