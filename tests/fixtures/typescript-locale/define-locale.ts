import { defineLocale } from './define-locale'

// Partial-locale fixture: defineLocale merges overrides over English.
export const ja = defineLocale({
  common: {
    save: '保存',
  },
})
