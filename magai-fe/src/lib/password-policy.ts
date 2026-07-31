/**
 * The password rule, in one place.
 *
 * Sign-up and password reset both have to state the rule and both have to
 * enforce it before spending a round trip. When they each owned a copy they
 * drifted, and the reset screen accepted passwords the API then rejected with a
 * raw policy string. Mirrors the backend's MAGAI_PASSWORD_MIN_LENGTH default.
 */
export const MIN_PASSWORD_LENGTH = 12;

export const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters, including a number.`;

/** Returns a message to show, or null when the password is acceptable. */
export function passwordProblem(password: string): string | null {
  if (!password) return "Enter your password.";
  if (password.length < MIN_PASSWORD_LENGTH)
    return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password))
    return "Include both letters and numbers.";
  return null;
}
