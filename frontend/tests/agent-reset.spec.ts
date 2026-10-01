import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
      enabled: true,
    },
  },
  example_geoserver_backends: [
    {
      url: "https://geoserver.mapx.org/geoserver/",
      name: "MapX",
      description: "Example GeoServer",
    },
  ],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session",
};

test.describe("AgentInterface reset button", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("reset button is visible in the Map Assistant header", async ({ page }) => {
    const resetBtn = page.getByTestId("agent-reset-button");
    await expect(resetBtn).toBeVisible();
    await expect(resetBtn).toHaveAttribute("aria-label", "Reset application");
  });

  test("reset button shows confirmation dialog and cancels on dismiss", async ({
    page,
  }) => {
    let dialogMessage = "";
    page.on("dialog", async (dialog) => {
      dialogMessage = dialog.message();
      await dialog.dismiss();
    });

    const resetBtn = page.getByTestId("agent-reset-button");
    await resetBtn.click();
    await page.waitForTimeout(100);

    expect(dialogMessage).toContain("Reset the Map Assistant");
  });

  test("reset button clears chat messages when confirmed", async ({ page }) => {
    await page.waitForFunction(() => !!(window as any).useChatInterfaceStore);
    await page.evaluate(() => {
      (window as any).useChatInterfaceStore.getState().setMessages([
        { type: "human", content: "seeded question" },
        { type: "ai", content: "seeded answer" },
      ]);
    });
    await expect(page.getByText("seeded question")).toBeVisible();
    await expect(page.getByText("seeded answer")).toBeVisible();

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();

    await expect(page.getByText("seeded question")).toHaveCount(0);
    await expect(page.getByText("seeded answer")).toHaveCount(0);
    const msgs = await page.evaluate(
      () => (window as any).useChatInterfaceStore.getState().messages.length,
    );
    expect(msgs).toBe(0);
  });

  test("reset aborts an in-flight stream and late events do not repopulate", async ({
    page,
  }) => {
    await page.waitForFunction(() => !!(window as any).useChatInterfaceStore);
    // Mock /chat/stream: emits a token, then would send a result after 1.5s
    // unless the request signal is aborted first.
    await page.evaluate(() => {
      const w = window as any;
      w.__streamAborted = false;
      const originalFetch = window.fetch;
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.href
              : input.url;
        if (url.includes("/chat/stream")) {
          const enc = new TextEncoder();
          const stream = new ReadableStream({
            start(controller) {
              const onAbort = () => {
                w.__streamAborted = true;
                clearTimeout(t);
                controller.error(new DOMException("Aborted", "AbortError"));
              };
              init?.signal?.addEventListener("abort", onAbort);
              controller.enqueue(
                enc.encode('event: llm_token\ndata: {"token":"partial"}\n\n'),
              );
              const t = setTimeout(() => {
                const data = {
                  messages: [
                    { type: "human", content: "late question" },
                    { type: "ai", content: "late answer" },
                  ],
                  geodata_results: [],
                };
                controller.enqueue(
                  enc.encode(`event: result\ndata: ${JSON.stringify(data)}\n\n`),
                );
                controller.close();
              }, 1500);
            },
          });
          return new Response(stream, {
            status: 200,
            headers: { "Content-Type": "text/event-stream" },
          });
        }
        if (url.includes("/chat/cancel")) {
          return new Response("{}", { status: 200 });
        }
        return originalFetch(input, init);
      };
    });

    const input = page.getByPlaceholder(
      "Ask about maps, search for data, or request analysis...",
    );
    await input.fill("late question");
    await input.press("Enter");
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as any).useChatInterfaceStore.getState().isStreaming,
        ),
      )
      .toBe(true);

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();

    await expect
      .poll(() => page.evaluate(() => (window as any).__streamAborted))
      .toBe(true);

    // Wait past the point where the mocked result would have arrived.
    await page.waitForTimeout(2000);
    const state = await page.evaluate(() => {
      const s = (window as any).useChatInterfaceStore.getState();
      return { n: s.messages.length, streaming: s.isStreaming };
    });
    expect(state.n).toBe(0);
    expect(state.streaming).toBe(false);
    await expect(page.getByText("late answer")).toHaveCount(0);
  });
});
