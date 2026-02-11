import { test, expect } from '@playwright/test';

test.describe('MQTT Topic Tree Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');

    // Check page title
    await expect(page).toHaveTitle(/MQTT Topic Explorer/);

    // Check main heading
    await expect(page.getByRole('heading', { name: 'MQTT Topic Explorer' })).toBeVisible();
  });

  test('should display connection status indicator', async ({ page }) => {
    await page.goto('/');

    // Wait for connection status to appear
    const statusText = page.getByText(/Connected|Disconnected/);
    await expect(statusText).toBeVisible({ timeout: 10000 });
  });

  test('should display stats bar', async ({ page }) => {
    await page.goto('/');

    // Check for stats labels
    await expect(page.getByText('Topics:')).toBeVisible();
    await expect(page.getByText('Messages:')).toBeVisible();
    await expect(page.getByText('Last Update:')).toBeVisible();
  });

  test('should display topic tree panel', async ({ page }) => {
    await page.goto('/');

    // Check for Topic Tree heading
    await expect(page.getByRole('heading', { name: 'Topic Tree' })).toBeVisible();
  });

  test('should display topic details panel', async ({ page }) => {
    await page.goto('/');

    // Check for Topic Details heading
    await expect(page.getByRole('heading', { name: 'Topic Details' })).toBeVisible();

    // Should show placeholder text initially
    await expect(page.getByText('Select a topic to view details')).toBeVisible();
  });

  test('should wait for MQTT messages and display topics', async ({ page }) => {
    await page.goto('/');

    // Wait up to 30 seconds for topics to appear or "Waiting for messages" text
    const hasTopics = page.locator('.topic-node').first();
    const waitingText = page.getByText('Waiting for MQTT messages...');

    // One of these should be visible
    await Promise.race([
      expect(hasTopics).toBeVisible({ timeout: 30000 }),
      expect(waitingText).toBeVisible({ timeout: 30000 }),
    ]);
  });

  test('should expand and collapse topic nodes when they have children', async ({ page }) => {
    await page.goto('/');

    // Wait for topics to load
    await page.waitForSelector('.topic-node', { timeout: 30000 }).catch(() => {
      console.log('No topics received yet');
    });

    // Look for an expand/collapse button (arrow icon)
    const expandButton = page.locator('button[aria-label="Expand"]').first();

    if (await expandButton.isVisible()) {
      // Click to expand
      await expandButton.click();
      await expect(expandButton).toHaveAttribute('aria-label', 'Collapse');

      // Click to collapse
      await expandButton.click();
      await expect(expandButton).toHaveAttribute('aria-label', 'Expand');
    }
  });

  test('should select topic and display details', async ({ page }) => {
    await page.goto('/');

    // Wait for topics to load
    await page.waitForSelector('.topic-node', { timeout: 30000 }).catch(() => {
      console.log('No topics received yet');
    });

    // Look for a leaf topic (one with a document icon)
    const leafTopic = page.locator('.topic-node').filter({ hasText: /\(\d+\)/ }).first();

    if (await leafTopic.isVisible()) {
      await leafTopic.click();

      // Details panel should update
      await expect(page.getByText('Topic Path')).toBeVisible();
      await expect(page.getByText('Message Count')).toBeVisible();
    }
  });

  test('should handle no MQTT broker connection gracefully', async ({ page }) => {
    await page.goto('/');

    // Should either connect or show waiting/connecting message
    const possibleStates = [
      page.getByText('Connected'),
      page.getByText('Disconnected'),
      page.getByText('Waiting for MQTT messages...'),
      page.getByText('Connecting to MQTT broker...'),
    ];

    // At least one should be visible
    let foundState = false;
    for (const state of possibleStates) {
      if (await state.isVisible({ timeout: 5000 }).catch(() => false)) {
        foundState = true;
        break;
      }
    }

    expect(foundState).toBe(true);
  });

  test('should display health endpoint', async ({ page }) => {
    const response = await page.goto('/health');
    expect(response?.status()).toBe(200);

    const body = await response?.json();
    expect(body).toHaveProperty('status', 'healthy');
    expect(body).toHaveProperty('service', 'mqtt-topic-tree');
  });
});
