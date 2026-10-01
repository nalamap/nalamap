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

  test("reset during slow settings init prevents the stream from starting", async ({
    page,
  }) => {
    await page.waitForFunction(
      () => !!(window as any).useChatInterfaceStore && !!(window as any).useSettingsStore,
    );
    await page.evaluate(() => {
      const w = window as any;
      w.__streamRequests = 0;
      w.useSettingsStore.setState({
        initializeIfNeeded: () => new Promise<void>((r) => setTimeout(r, 1500)),
      });
      const originalFetch = window.fetch;
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.includes("/chat/stream")) {
          w.__streamRequests++;
          return new Response("", { status: 200 });
        }
        return originalFetch(input, init);
      };
    });

    const input = page.getByPlaceholder(
      "Ask about maps, search for data, or request analysis...",
    );
    await input.fill("pending question");
    await input.press("Enter");
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).useChatInterfaceStore.getState().isStreaming),
      )
      .toBe(true);

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();

    await page.waitForTimeout(2200);
    const state = await page.evaluate(() => {
      const w = window as any;
      const s = w.useChatInterfaceStore.getState();
      return { n: s.messages.length, streaming: s.isStreaming, reqs: w.__streamRequests };
    });
    expect(state.reqs).toBe(0);
    expect(state.n).toBe(0);
    expect(state.streaming).toBe(false);
    await expect(page.getByText("pending question")).toHaveCount(0);
  });

  test("late result while the cancel POST is pending is discarded", async ({
    page,
  }) => {
    await page.waitForFunction(() => !!(window as any).useChatInterfaceStore);
    await page.evaluate(() => {
      const w = window as any;
      w.__cancelPosted = false;
      const originalFetch = window.fetch;
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.includes("/chat/stream")) {
          const enc = new TextEncoder();
          const stream = new ReadableStream({
            start(controller) {
              init?.signal?.addEventListener("abort", () =>
                controller.error(new DOMException("Aborted", "AbortError")),
              );
              controller.enqueue(enc.encode('event: llm_token\ndata: {"token":"x"}\n\n'));
              setTimeout(() => {
                const data = {
                  messages: [
                    { type: "human", content: "late q" },
                    { type: "ai", content: "late a" },
                  ],
                  geodata_results: [],
                };
                try {
                  controller.enqueue(
                    enc.encode(`event: result\ndata: ${JSON.stringify(data)}\n\n`),
                  );
                  controller.close();
                } catch {
                  /* stream already aborted */
                }
              }, 600);
            },
          });
          return new Response(stream, {
            status: 200,
            headers: { "Content-Type": "text/event-stream" },
          });
        }
        if (url.includes("/chat/cancel")) {
          w.__cancelPosted = true;
          await new Promise((r) => setTimeout(r, 1500)); // slow ack
          return new Response("{}", { status: 200 });
        }
        return originalFetch(input, init);
      };
    });

    const input = page.getByPlaceholder(
      "Ask about maps, search for data, or request analysis...",
    );
    await input.fill("late q");
    await input.press("Enter");
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).useChatInterfaceStore.getState().isStreaming),
      )
      .toBe(true);

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();
    await expect.poll(() => page.evaluate(() => (window as any).__cancelPosted)).toBe(true);

    // Check while the cancel POST (1.5s) is still pending: the mocked result
    // arrives at ~0.6s and must not have been applied (reset's own clear only
    // runs after the POST resolves, so a late result would otherwise show here).
    await page.waitForTimeout(1000);
    const mid = await page.evaluate(
      () => (window as any).useChatInterfaceStore.getState().messages.length,
    );
    expect(mid).toBe(1); // only the human message appended before the stream

    await page.waitForTimeout(1500);
    const n = await page.evaluate(
      () => (window as any).useChatInterfaceStore.getState().messages.length,
    );
    expect(n).toBe(0);
    await expect(page.getByText("late a")).toHaveCount(0);
  });

  test("reset invalidates an in-flight map layer load", async ({ page }) => {
    await page.waitForFunction(() => !!(window as any).useLayerStore);
    await page.route("**/maps/m1/layers", async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "late-layer-1",
            name: "Late layer",
            data_type: "geojson",
            data_link: "https://example.com/late.geojson",
            z_index: 0,
            visible: true,
            payload: {},
          },
        ]),
      });
    });
    await page.evaluate(() => {
      (window as any).__loadDone = (window as any).useLayerStore
        .getState()
        .loadLayersForMap("m1")
        .then(() => true);
    });

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();

    await page.evaluate(() => (window as any).__loadDone);
    const count = await page.evaluate(
      () => (window as any).useLayerStore.getState().layers.length,
    );
    expect(count).toBe(0);
  });

  test("reset asks the backend to drop the conversation state", async ({ page }) => {
    await page.waitForFunction(
      () => !!(window as any).useSettingsStore?.getState().session_id,
    );
    const sid = await page.evaluate(
      () => (window as any).useSettingsStore.getState().session_id,
    );
    const resetReq = page.waitForRequest(
      (r) => r.url().includes("/chat/reset") && r.method() === "POST",
    );
    await page.route("**/chat/reset*", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    page.on("dialog", (dialog) => dialog.accept());
    await page.getByTestId("agent-reset-button").click();
    const req = await resetReq;
    expect(new URL(req.url()).searchParams.get("session_id")).toBe(sid);
  });
});
