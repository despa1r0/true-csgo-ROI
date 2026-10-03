// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { expect, it } from "vitest";
import { detailParams, useBrowseHistory, wearParams } from "./browseHistory";

function BrowseProbe() {
  const { params, update, back } = useBrowseHistory();
  return <>
    <output>{params.toString()}</output>
    <button onClick={() => update({ skin: "redline" })}>Skin</button>
    <button onClick={() => update({ wear: "Field-Tested" })}>Wear</button>
    <button onClick={() => update({ detail_variant: "normal-ft", listing: "123" })}>Listing</button>
    <button onClick={() => update({ tab: "compare", min_price: "10" }, true)}>Compare</button>
    <button onClick={() => back(detailParams)}>Back to listings</button>
    <button onClick={() => back(wearParams)}>Close wear</button>
  </>;
}

it("returns from calculator to the same detail, then one browse step at a time", async () => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const router = createMemoryRouter([{ path: "/", element: <BrowseProbe /> }, { path: "/calculator", element: <p>Calculator</p> }],
    { initialEntries: ["/?q=Redline&type=skin"] });
  const container = document.createElement("div");
  const root = createRoot(container);
  const click = async (label: string) => { await act(async () => [...container.querySelectorAll("button")].find((button) => button.textContent === label)!.click()); };
  try {
    await act(async () => root.render(<RouterProvider router={router} />));
    await click("Skin"); await click("Wear"); await click("Listing"); await click("Compare");
    const detailUrl = router.state.location.search;
    await act(async () => { await router.navigate("/calculator"); });
    await act(async () => { await router.navigate(-1); });
    expect(router.state.location.search).toBe(detailUrl);
    await click("Back to listings");
    expect(new URLSearchParams(router.state.location.search).get("wear")).toBe("Field-Tested");
    expect(new URLSearchParams(router.state.location.search).has("listing")).toBe(false);
    await click("Close wear");
    expect(new URLSearchParams(router.state.location.search).get("skin")).toBe("redline");
    await act(async () => { await router.navigate(-1); });
    expect(router.state.location.search).toBe("?q=Redline&type=skin");
    await act(async () => { await router.navigate(1); });
    expect(new URLSearchParams(router.state.location.search).get("skin")).toBe("redline");
  } finally { await act(async () => root.unmount()); router.dispose(); }
});

it("closes a deep-linked detail without navigating away from the site", async () => {
  const router = createMemoryRouter([{ path: "/", element: <BrowseProbe /> }],
    { initialEntries: ["/?q=Redline&skin=redline&wear=Field-Tested&detail_variant=normal-ft&listing=123"] });
  const container = document.createElement("div");
  const root = createRoot(container);
  try {
    await act(async () => root.render(<RouterProvider router={router} />));
    await act(async () => [...container.querySelectorAll("button")].find((button) => button.textContent === "Back to listings")!.click());
    expect(new URLSearchParams(router.state.location.search).has("detail_variant")).toBe(false);
    expect(new URLSearchParams(router.state.location.search).get("skin")).toBe("redline");
    expect(new URLSearchParams(router.state.location.search).get("wear")).toBe("Field-Tested");
  } finally { await act(async () => root.unmount()); router.dispose(); }
});
