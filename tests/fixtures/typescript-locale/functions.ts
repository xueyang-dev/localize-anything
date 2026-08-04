// Function-valued messages: template literals with ${expressions},
// conditionals, object-returning helpers, and array leaves.
export const en: Translations = {
  common: {
    save: 'Save',
    more: count => `${count} more ${count === 1 ? 'notification' : 'notifications'}`,
    waitingSince: minutes => (minutes < 1 ? 'just now' : `${minutes}m ago`),
    branchOff: () => ({ after: '', before: 'branch off ' }),
    bytes: size => size,
  },
  days: ["Sun", "Mon"],
}
