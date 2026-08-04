// Basic catalog fixture: plain strings, single and double quotes,
// placeholders, an array of weekday labels, and comments to preserve.
export const en = {
  common: {
    // Save button label
    save: 'Save',
    welcome: "Hello {name}",
    // Enum-like labels are translatable text in the web dashboard
    weekdaysShort: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  },
  errors: {
    retryCount: 'Retry {count} more time(s)',
  },
}
