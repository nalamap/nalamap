describe('Settings Page', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/settings/options', { fixture: 'settingsOptions.json' }).as('getSettingsOptions')
  })

  it('loads settings options from the backend and populates the UI', () => {
    cy.visit('/settings')
    cy.wait('@getSettingsOptions')

    cy.contains('h1', 'Settings').should('be.visible')

    cy.get('[data-cy=model-provider-select] option').should('have.length', 2)
    cy.get('[data-cy=model-provider-select]').should('have.value', 'openai')

    cy.get('[data-cy=model-name-select] option').then(($options) => {
      const values = [...$options].map((option) => (option as HTMLOptionElement).value)
      expect(values).to.include.members(['gpt-4o', 'gpt-4o-mini'])
    })

    cy.get('[data-cy=system-prompt]').should('have.value', 'You are NaLaMap, a helpful assistant.')

    cy.get('[data-cy=tool-add-select] option').should('contain.text', 'chat').and('contain.text', 'search')

    cy.get('[data-cy=portal-add-select] option').then(($options) => {
      const optionTexts = [...$options].map((option) => (option as HTMLOptionElement).text)
      expect(optionTexts).to.include.members(['https://data.example.com', 'https://open.example.org'])
    })
  })
})
