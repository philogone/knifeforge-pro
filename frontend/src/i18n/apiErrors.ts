import { ApiError } from "@/composables/useApi";

/**
 * The API answers in English (it is also used by scripts). The screen speaks the maker's
 * language: known server messages map to an i18n key, unknown ones are shown as sent.
 */
const EXACT: Record<string, string> = {
  "Material not found": "apiError.materialNotFound",
  "Knife model not found": "apiError.modelNotFound",
  "Treatment recipe not found": "apiError.recipeNotFound",
  "Saw blade not found": "apiError.sawNotFound",
  "Order not found": "apiError.orderNotFound",
  "Design not found": "apiError.designNotFound",
  "Too many attempts, try again shortly": "apiError.rateLimited",
  "Invalid credentials": "apiError.invalidCredentials",
  "Read-only demo": "apiError.readOnlyDemo",
  "Create the account first": "apiError.setupFirst",
  "The account already exists": "apiError.accountExists",
  "Backup folder not writable": "apiError.backupFolder",
  "Recipe is used by one or more knife models": "apiError.recipeInUse",
  "Material is used by one or more knife models": "apiError.materialInUse",
  "Knife model is used by one or more orders": "apiError.modelInUse",
  "Only draft orders can have their lines edited": "apiError.onlyDraftEdit",
  "Only draft or cancelled orders can be deleted": "apiError.onlyDraftDelete",
  "Only confirmed orders can be marked completed": "apiError.onlyConfirmedComplete",
  "Only draft or confirmed orders can be cancelled": "apiError.onlyOpenCancel",
  "Only draft orders can be confirmed": "apiError.onlyDraftConfirm",
  "Resulting stock cannot be negative": "apiError.negativeStock",
  "purchase_price/shipping_cost require a positive quantity_delta": "apiError.priceNeedsQuantity",
  "Blank is larger than the material's standard sheet in both orientations": "apiError.blankTooLargeSheet",
  "Blank length (plus kerf) is longer than the material's standard stock length": "apiError.blankTooLong",
  "Cutting optimization only applies to LENGTH materials": "apiError.optimizerLengthOnly",
  "Material has no standard sheet dimensions set — required for AREA yield calculations": "apiError.noSheetSize",
  "Material has no standard_length_mm set — required for LENGTH yield calculations": "apiError.noBarLength",
  "Material has no standard_length_mm set": "apiError.noBarLength",
  "Material needs standard_length_mm and standard_width_mm to nest parts on it": "apiError.nestNeedsSize",
  "Nesting only applies to LENGTH (bar) and AREA (sheet) materials": "apiError.nestBarOrSheet",
  "Offset collapses the shape": "apiError.offsetCollapses",
  "Shape is empty or degenerate": "apiError.shapeDegenerate",
  "The design has nothing to draw": "apiError.nothingToDraw",
  "The design has nothing to export": "apiError.nothingToExport",
  "blank_width_mm is required for AREA materials": "apiError.blankWidthRequired",
  "image must be a base64 JPEG, PNG or WebP data URL": "apiError.badImage",
};

/** messages built with values: matched on their fixed start */
const PREFIX: [string, string][] = [
  ["Too many parts to nest", "apiError.tooManyParts"],
];

/** the message to put on screen for any failure (API error, network down, bug) */
export function errorMessage(err: unknown, t: (key: string, vars?: Record<string, string | number>) => string, fallbackKey = "common.error"): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return t("apiError.network");
    const key = EXACT[err.message] ?? PREFIX.find(([p]) => err.message.startsWith(p))?.[1];
    if (key) return t(key);
    if (err.status === 422) return t("apiError.validation", { detail: err.message });
    if (err.status >= 500) return t("apiError.server");
    return err.message || t(fallbackKey);
  }
  // fetch() itself failed: the backend is not reachable
  if (err instanceof TypeError) return t("apiError.network");
  return t(fallbackKey);
}
