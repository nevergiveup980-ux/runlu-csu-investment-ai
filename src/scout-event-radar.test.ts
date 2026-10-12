import { classifyPressRelease, normalizeMaterialEvent } from "./scout-event-radar";

const expectEqual = (actual: unknown, expected: unknown, message: string) => {
  if (actual !== expected) throw new Error(`${message}: got ${String(actual)} expected ${String(expected)}`);
};

expectEqual(
  classifyPressRelease({ title: "Company reports quarterly financial results" }),
  "EARNINGS",
  "earnings classification",
);
expectEqual(
  classifyPressRelease({ title: "Company updates 2027 guidance" }),
  "GUIDANCE",
  "guidance classification",
);
expectEqual(
  classifyPressRelease({ title: "Company to acquire rival in strategic combination" }),
  "M_AND_A",
  "M&A classification",
);
expectEqual(
  classifyPressRelease({ title: "Company appoints new Chief Financial Officer" }),
  "MANAGEMENT_CHANGE",
  "management classification",
);
expectEqual(
  classifyPressRelease({ title: "Company announces bought deal offering" }),
  "CAPITAL_RAISE",
  "capital raise classification",
);
expectEqual(
  classifyPressRelease({ title: "Company increases quarterly dividend" }),
  "DIVIDEND_CHANGE",
  "dividend classification",
);
expectEqual(
  classifyPressRelease({ title: "Company faces class action lawsuit" }),
  "LITIGATION",
  "litigation classification",
);
expectEqual(
  classifyPressRelease({ title: "Company opens new research facility" }),
  "MATERIAL_NEWS",
  "fallback material classification",
);

const normalized = normalizeMaterialEvent({
  id: "abc-123",
  datetime: "2026-10-12T12:30:00",
  title: "<b>Quarterly results announced</b>",
  body: "<p>Revenue improved.</p>",
});
if (!normalized) throw new Error("normalization should produce an event");
expectEqual(normalized.id, "abc-123", "event id");
expectEqual(normalized.type, "EARNINGS", "normalized event type");
expectEqual(normalized.sourceType, "OFFICIAL_PRESS_RELEASE", "source type");
if (normalized.title.includes("<")) throw new Error("HTML should be removed from event title");

if (normalizeMaterialEvent({ id: "", title: "Missing id" }) !== null) {
  throw new Error("event without id must be rejected");
}

console.log("scout-event-radar safety tests passed");
