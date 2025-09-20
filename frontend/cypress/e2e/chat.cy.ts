describe('Chat Interface', () => {
  const message = 'Hello NaLaMap'

  beforeEach(() => {
    cy.intercept('GET', '**/settings/options', { fixture: 'settingsOptions.json' }).as('getSettingsOptions')
  })

  it('allows sending a message and displays the agent response', () => {
    cy.intercept('POST', '**/chat', (req) => {
      expect(req.body.query).to.eq(message)
      req.reply({
        statusCode: 200,
        body: {
          geodata_results: [],
          messages: [
            { type: 'human', content: message },
            { type: 'ai', content: 'Hi from NaLaMap!' }
          ]
        }
      })
    }).as('chatRequest')

    cy.visit('/')
    cy.wait('@getSettingsOptions')

    cy.contains('h2', 'Map Assistant').should('be.visible')

    cy.get('textarea[placeholder*="Type a chat command"]').type(message)
    cy.get('button[title="Send"]').click()

    cy.wait('@chatRequest')

    cy.contains('.text-sm', message).should('be.visible')
    cy.contains('.text-sm', 'Hi from NaLaMap!').should('be.visible')
  })
})
