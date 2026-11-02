/**
 * Mock Backend Service simulating the contracts for VALENCE.
 */

const VISION_PROFILES = {
  blurry: {
    success: false,
    observations: [],
    text: "⚠️ **[MOCK VISION RESPONSE]** Image quality is insufficient for reliable interpretation. The image appears blurry or low-resolution.",
  },
  unknown: {
    success: false,
    observations: [
      "[MOCK] Unknown equipment enclosure visible — no matching product family identified.",
      "[MOCK] No nameplate or model number matched to indexed documentation.",
    ],
    text: "⚠️ **[MOCK VISION RESPONSE]** The equipment visible in the image does not match any documentation in the indexed corpus.",
  },
  ambiguous: {
    success: false,
    observations: [
      "[MOCK] S7-1200 series CPU housing detected — model variant cannot be determined.",
      "[MOCK] Product label partially obscured.",
    ],
    text: "⚠️ **[MOCK VISION RESPONSE]** The equipment identity is ambiguous from the image provided. Verify model on physical label.",
  },
  normal: {
    success: true,
    observations: [
      "[MOCK] RUN/STOP indicator: solid green — CPU is in RUN state.",
      "[MOCK] ERROR LED: off — no active hardware or firmware fault detected.",
      "[MOCK] MAINT LED: off — no maintenance mode active.",
      "[MOCK] LINK TX/RX LED: flashing green — Ethernet communication active.",
    ],
    text: null,
  },
}

function classifyImage(filename) {
  const lower = (filename || "").toLowerCase()
  if (lower.includes("blurry")) return "blurry"
  if (lower.includes("unknown")) return "unknown"
  if (lower.includes("ambiguous")) return "ambiguous"
  return "normal"
}

export function answerQuestionMock(question, equipmentModel, indexedDocs = {}) {
  const qLower = question.toLowerCase()
  const negativeKeywords = ["torque specification", "cylinder head bolt", "gearbox lubricant", "hydraulic pump rotor"]
  const isNegative = negativeKeywords.some((kw) => qLower.includes(kw))

  const docKeys = Object.keys(indexedDocs)
  if (docKeys.length === 0) {
    return {
      text: "No indexed documents available in the knowledge base. Please upload an equipment manual or SOP in the Document Library first.",
      evidence: [],
      insufficient_evidence: true,
      observations: [],
    }
  }

  if (isNegative) {
    return {
      text: "Retrieved SOP context does not substantiate an answer for this query. The documentation contains no technical data for the specified maintenance parameter.",
      evidence: [],
      insufficient_evidence: true,
      observations: [],
    }
  }

  const firstDoc = indexedDocs[docKeys[0]]
  const model = equipmentModel || firstDoc.equipment_model || "SIMATIC S7-1200"

  const evidence = [
    {
      source_id: `${firstDoc.document_id}#p1#c0`,
      chunk: {
        chunk_id: `${firstDoc.document_id}#p1#c0`,
        document_id: firstDoc.document_id,
        filename: docKeys[0],
        page: 1,
        text: `Standard Operating Procedure for ${model}: Before starting maintenance, ensure system is powered off and lockout-tagout (LOTO) protocols are engaged. Verify indicator LEDs RUN/STOP, ERROR, and MAINT status.`,
        equipment_model: model,
        synthetic: Boolean(firstDoc.synthetic),
      },
    },
    {
      source_id: `${firstDoc.document_id}#p2#c1`,
      chunk: {
        chunk_id: `${firstDoc.document_id}#p2#c1`,
        document_id: firstDoc.document_id,
        filename: docKeys[0],
        page: 2,
        text: `Troubleshooting guide: If ERROR LED flashes red, check diagnostics buffer via engineering station. Inspect communication links and power rail voltage levels (24V DC nominal).`,
        equipment_model: model,
        synthetic: Boolean(firstDoc.synthetic),
      },
    },
  ]

  const citations = evidence.map((e) => `[${e.source_id}]`).join(" ")
  const answerText = `According to ${citations}, the standard maintenance procedure for ${model} indicates inspecting module status indicators, verifying nominal 24V supply, and consulting the diagnostic buffer prior to component replacement.`

  return {
    text: answerText,
    evidence,
    insufficient_evidence: false,
    observations: [],
  }
}

export function answerWithImageMock(question, imageFileName, equipmentModel, indexedDocs = {}) {
  const profileKey = classifyImage(imageFileName)
  const profile = VISION_PROFILES[profileKey]

  if (!profile.success) {
    return {
      text: profile.text,
      evidence: [],
      insufficient_evidence: true,
      observations: profile.observations,
    }
  }

  const baseAnswer = answerQuestionMock(question, equipmentModel, indexedDocs)
  const observations = [
    ...profile.observations,
    `[MOCK] Image analysed: '${imageFileName}' — visual state is consistent with documented operating conditions.`,
  ]

  return {
    ...baseAnswer,
    observations,
  }
}

