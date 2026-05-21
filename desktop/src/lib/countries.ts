/**
 * Country code utilities — flag conversion + bilingual names for OSINT coverage.
 */

export function countryCodeToFlag(code: string): string {
  return [...code.toUpperCase()]
    .map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
    .join("");
}

export const COUNTRY_NAMES: Record<string, { he: string; en: string }> = {
  IL: { he: "ישראל", en: "Israel" },
  IR: { he: "איראן", en: "Iran" },
  LB: { he: "לבנון", en: "Lebanon" },
  PS: { he: "פלסטין", en: "Palestine" },
  SY: { he: "סוריה", en: "Syria" },
  IQ: { he: "עיראק", en: "Iraq" },
  YE: { he: "תימן", en: "Yemen" },
  SA: { he: "סעודיה", en: "Saudi Arabia" },
  AE: { he: "איחוד האמירויות", en: "UAE" },
  JO: { he: "ירדן", en: "Jordan" },
  EG: { he: "מצרים", en: "Egypt" },
  TR: { he: "טורקיה", en: "Turkey" },
  RU: { he: "רוסיה", en: "Russia" },
  UA: { he: "אוקראינה", en: "Ukraine" },
  US: { he: "ארה\"ב", en: "United States" },
  CN: { he: "סין", en: "China" },
  TW: { he: "טייוואן", en: "Taiwan" },
  KP: { he: "צפון קוריאה", en: "North Korea" },
  KR: { he: "דרום קוריאה", en: "South Korea" },
  JP: { he: "יפן", en: "Japan" },
  PK: { he: "פקיסטן", en: "Pakistan" },
  IN: { he: "הודו", en: "India" },
  AF: { he: "אפגניסטן", en: "Afghanistan" },
  PH: { he: "פיליפינים", en: "Philippines" },
  VN: { he: "וייטנאם", en: "Vietnam" },
  MM: { he: "מיאנמר", en: "Myanmar" },
  SD: { he: "סודן", en: "Sudan" },
  LY: { he: "לוב", en: "Libya" },
  SO: { he: "סומליה", en: "Somalia" },
  ET: { he: "אתיופיה", en: "Ethiopia" },
  ER: { he: "אריתריאה", en: "Eritrea" },
  GB: { he: "בריטניה", en: "United Kingdom" },
  FR: { he: "צרפת", en: "France" },
  DE: { he: "גרמניה", en: "Germany" },
  BY: { he: "בלארוס", en: "Belarus" },
  GE: { he: "גאורגיה", en: "Georgia" },
  AM: { he: "ארמניה", en: "Armenia" },
  AZ: { he: "אזרבייג'ן", en: "Azerbaijan" },
};
