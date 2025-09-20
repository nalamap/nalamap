import './commands'

declare global {
  namespace Cypress {
    interface Chainable {
      /** Custom command placeholder */
    }
  }
}

// Prevent tests from failing on uncaught exceptions from third-party scripts
Cypress.on('uncaught:exception', () => false)
