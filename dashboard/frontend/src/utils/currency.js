/**
 * Utility functions for currency conversion and Indian Rupee (₹ / INR) formatting.
 *
 * Exchange rate: 1 USD = 83 INR
 */

export const USD_TO_INR = 83;

/**
 * Converts a USD amount to INR and formats it using the standard Indian Rupee notation.
 * e.g., 125.40 USD -> ₹10,408.20
 *
 * @param {number|string} usdAmount - The monetary value in USD
 * @returns {string} - Formatted currency string with ₹ symbol and Indian comma grouping
 */
export function formatINR(usdAmount) {
  if (usdAmount == null || isNaN(usdAmount)) return '₹0.00';
  const inr = Number(usdAmount) * USD_TO_INR;
  return `₹${inr.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Formats a value already in INR.
 *
 * @param {number|string} inrAmount - The monetary value in INR
 * @returns {string} - Formatted currency string with ₹ symbol and Indian comma grouping
 */
export function formatDirectINR(inrAmount) {
  if (inrAmount == null || isNaN(inrAmount)) return '₹0.00';
  return `₹${Number(inrAmount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
