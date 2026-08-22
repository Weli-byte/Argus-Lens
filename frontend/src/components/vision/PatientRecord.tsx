"use client";

import React from "react";
import {
  BadgeCheck,
  HeartPulse,
  IdCard,
  PhoneCall,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   HASTA KÜNYESİ

   Gerçek bir hastane kaydında bulunan ama arayüzde eksik olan idari alanlar:
   protokol no, kimlik, sigorta, acil durumda aranacak yakın, sorumlu hekim,
   yaşam tarzı, aile öyküsü, aşı kayıtları.

   Hepsi backend'de tek bir `admin_record` JSON alanında saklanır — her yeni
   alan için şemaya sütun eklemek gerekmiyor.

   TC kimlik numarası BİLEREK yok: uygulamanın hiçbir yerinde doğrulanmıyor,
   saklanması gereksiz risk. Protokol numarası kurum içi takip için yeterli.
   ────────────────────────────────────────────────────────────────────────── */

export type AdminRecord = {
  protocol_no?: string;
  full_name?: string;
  birth_date?: string;
  phone?: string;
  insurance_provider?: string;
  insurance_no?: string;
  emergency_name?: string;
  emergency_relation?: string;
  emergency_phone?: string;
  primary_physician?: string;
  clinic?: string;
  smoking?: string;
  alcohol?: string;
  organ_donor?: boolean;
  family_history?: string[];
  vaccinations?: string[];
};

type Props = {
  record: AdminRecord;
  onChange: (patch: Partial<AdminRecord>) => void;
};

const SMOKING = ["Hiç kullanmadı", "Bırakmış", "Aktif içici"];
const ALCOHOL = ["Kullanmıyor", "Nadiren", "Düzenli"];

export default function PatientRecord({ record, onChange }: Props) {
  const t = useT();
  const set = (k: keyof AdminRecord) => (v: string) => onChange({ [k]: v });

  return (
    <section className="prof-grid" data-reveal-block>
      {/* ── Kimlik ──────────────────────────────────────────────────────── */}
      <div className="vis-plate">
        <p className="vis-plate-head t-dial">
          <IdCard className="size-3.5" /> {t("Kimlik")}
        </p>

        <dl className="prof-rows">
          <Row label={t("Protokol no")}>
            <span className="t-measure">{record.protocol_no || "—"}</span>
          </Row>
          <FieldRow
            label={t("Ad soyad")}
            value={record.full_name}
            onChange={set("full_name")}
            placeholder={t("Ad Soyad")}
          />
          <FieldRow
            label={t("Doğum tarihi")}
            value={record.birth_date}
            onChange={set("birth_date")}
            placeholder={t("GG.AA.YYYY")}
          />
          <FieldRow
            label={t("Telefon")}
            value={record.phone}
            onChange={set("phone")}
            placeholder={t("+90 5xx xxx xx xx")}
            type="tel"
          />
        </dl>
      </div>

      {/* ── Sigorta ─────────────────────────────────────────────────────── */}
      <div className="vis-plate">
        <p className="vis-plate-head t-dial">
          <ShieldCheck className="size-3.5" /> {t("Sigorta")}
        </p>
        <dl className="prof-rows">
          <FieldRow
            label={t("Kurum")}
            value={record.insurance_provider}
            onChange={set("insurance_provider")}
            placeholder={t("SGK / Özel")}
          />
          <FieldRow
            label={t("Poliçe / sicil no")}
            value={record.insurance_no}
            onChange={set("insurance_no")}
            placeholder={t("—")}
          />
          <Row label={t("Organ bağışı")}>
            <button
              type="button"
              role="switch"
              aria-checked={!!record.organ_donor}
              onClick={() => onChange({ organ_donor: !record.organ_donor })}
              className="prof-switch"
            >
              <span className="prof-switch-dot" />
              <span>{t(record.organ_donor ? "Bağışçı" : "Kayıtlı değil")}</span>
            </button>
          </Row>
        </dl>
      </div>

      {/* ── Acil durum ──────────────────────────────────────────────────── */}
      <div className="vis-plate prof-plate-alert">
        <p className="vis-plate-head t-dial">
          <PhoneCall className="size-3.5" style={{ color: "var(--state-critical)" }} />
          {t("Acil durumda aranacak")}
        </p>
        <dl className="prof-rows">
          <FieldRow
            label={t("Ad soyad")}
            value={record.emergency_name}
            onChange={set("emergency_name")}
            placeholder={t("Yakınının adı")}
          />
          <FieldRow
            label={t("Yakınlık")}
            value={record.emergency_relation}
            onChange={set("emergency_relation")}
            placeholder={t("Eş / kardeş / veli")}
          />
          <FieldRow
            label={t("Telefon")}
            value={record.emergency_phone}
            onChange={set("emergency_phone")}
            placeholder={t("+90 5xx xxx xx xx")}
            type="tel"
          />
        </dl>
      </div>

      {/* ── Sorumlu hekim ───────────────────────────────────────────────── */}
      <div className="vis-plate">
        <p className="vis-plate-head t-dial">
          <Stethoscope className="size-3.5" /> {t("Sorumlu hekim")}
        </p>
        <dl className="prof-rows">
          <FieldRow
            label={t("Hekim")}
            value={record.primary_physician}
            onChange={set("primary_physician")}
            placeholder={t("Dr. —")}
          />
          <FieldRow
            label={t("Birim")}
            value={record.clinic}
            onChange={set("clinic")}
            placeholder={t("Göz Hastalıkları")}
          />
        </dl>
      </div>

      {/* ── Yaşam tarzı ─────────────────────────────────────────────────── */}
      <div className="vis-plate">
        <p className="vis-plate-head t-dial">
          <HeartPulse className="size-3.5" /> {t("Yaşam tarzı")}
        </p>
        <dl className="prof-rows">
          <Row label={t("Sigara")}>
            <Choice
              options={SMOKING}
              value={record.smoking}
              onSelect={(v) => onChange({ smoking: v })}
            />
          </Row>
          <Row label={t("Alkol")}>
            <Choice
              options={ALCOHOL}
              value={record.alcohol}
              onSelect={(v) => onChange({ alcohol: v })}
            />
          </Row>
        </dl>
      </div>

      {/* ── Aile öyküsü + aşılar ────────────────────────────────────────── */}
      <div className="vis-plate">
        <p className="vis-plate-head t-dial">
          <BadgeCheck className="size-3.5" /> {t("Öykü ve aşılar")}
        </p>
        <div className="prof-rows">
          <ChipList
            label={t("Aile öyküsü")}
            items={record.family_history ?? []}
            onChange={(items) => onChange({ family_history: items })}
            placeholder={t("Hipertansiyon (baba)")}
          />
          <ChipList
            label={t("Aşılar")}
            items={record.vaccinations ?? []}
            onChange={(items) => onChange({ vaccinations: items })}
            placeholder={t("Tetanoz (2024)")}
          />
        </div>
      </div>
    </section>
  );
}

/* ── Parçalar ────────────────────────────────────────────────────────────── */
function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const t = useT();
  return (
    <div className="prof-row">
      <dt className="t-dial">{t(label)}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function FieldRow({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value?: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  const t = useT();
  return (
    <div className="prof-row">
      <label className="t-dial">{t(label)}</label>
      <input
        className="prof-input"
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
    </div>
  );
}

function Choice({
  options,
  value,
  onSelect,
}: {
  options: readonly string[];
  value?: string;
  onSelect: (v: string) => void;
}) {
  const t = useT();
  return (
    <div className="prof-choice">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={value === o}
          onClick={() => onSelect(o)}
          className="prof-choice-btn"
        >
          {t(o)}
        </button>
      ))}
    </div>
  );
}

function ChipList({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = React.useState("");

  const add = () => {
    const v = draft.trim();
    if (!v || items.includes(v)) return;
    onChange([...items, v]);
    setDraft("");
  };

  const t = useT();
  return (
    <div className="prof-chiplist">
      <p className="t-dial">{t(label)}</p>
      <div className="prof-chips">
        {items.length === 0 && <span className="prof-empty">{t("Kayıt yok")}</span>}
        {items.map((it) => (
          <span key={it} className="prof-chip">
            {it}
            <button
              type="button"
              onClick={() => onChange(items.filter((x) => x !== it))}
              aria-label={`${it} — ${t("sil")}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="prof-chip-add">
        <input
          className="prof-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <button type="button" className="btn btn-ghost" onClick={add}>
          {t("Ekle")}
        </button>
      </div>
    </div>
  );
}
