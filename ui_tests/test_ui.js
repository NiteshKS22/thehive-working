const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT_DIR = 'C:\\Users\\NITESH KUMAR\\.gemini\\antigravity\\brain\\62693542-6113-4eda-b14e-a046fdedf03b';

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log('Navigating to http://localhost/#!/nv/cases');
    await page.goto('http://localhost/#!/nv/cases');

    // Wait for potential login or dashboard
    await page.waitForTimeout(3000);

    if (await page.isVisible('input[name="user"]')) {
        console.log('Logging in...');
        await page.fill('input[name="user"]', 'admin');
        await page.fill('input[name="password"]', 'secret');
        await page.click('button[type="submit"]');
        await page.waitForNavigation();
    }

    await page.screenshot({ path: path.join(OUT_DIR, '01_cases_dashboard.png') });

    console.log('Clicking New Case...');
    await page.click('button:has-text("New case")');
    await page.waitForSelector('input[name="title"]', { state: 'visible' });
    await page.fill('input[name="title"]', 'Enterprise E2E Playwright Case');
    await page.fill('textarea[name="description"]', 'Full End-to-End Enterprise Scenario');

    await page.screenshot({ path: path.join(OUT_DIR, '02_create_case.png') });
    await page.click('button:has-text("Create case")');

    // Wait for details page to load
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(OUT_DIR, '03_case_details.png') });

    // Enterprise Button Tests on Header
    console.log('Testing Flag Button...');
    const flagBtn = await page.$('a[ng-click="switchFlag()"]');
    if (flagBtn) await flagBtn.click();
    await page.waitForTimeout(3000);

    // Open Tasks
    console.log('Testing Tasks Tab...');
    await page.click('a[heading="Tasks"]');
    await page.waitForTimeout(3000);

    // Wait for Add task button
    const addTaskBtn = await page.$('button[ng-click="addTask()"]');
    if (addTaskBtn) {
        await addTaskBtn.click();
        await page.fill('input[ng-model="task.title"]', 'Enterprise Validation Task');
        await page.click('button:has-text("Save")');
        await page.waitForTimeout(3000);
    } else {
        console.log('Add Task button not found');
    }
    await page.screenshot({ path: path.join(OUT_DIR, '04_tasks_tab.png') });

    // Open Observables
    console.log('Testing Observables Tab...');
    await page.click('a[heading="Observables"]');
    await page.waitForTimeout(3000);

    const addObsBtn = await page.$('button[ng-click="openAddForm()"]');
    if (addObsBtn) {
        await addObsBtn.click();
        await page.fill('input[ng-model="newData.data"]', 'enterprise-playwright-test.com');
        await page.click('button:has-text("Create observable(s)")');
        await page.waitForTimeout(3000);
    } else {
        console.log('Add Observable button not found');
    }
    await page.screenshot({ path: path.join(OUT_DIR, '05_observables_tab.png') });

    // Open Pages
    console.log('Testing Pages Tab...');
    await page.click('a[heading="Pages"]');
    await page.waitForTimeout(3000);

    const addPageBtn = await page.$('button[ng-click="addPage()"]');
    if (addPageBtn) {
        await addPageBtn.click();
        await page.fill('input[ng-model="newPage.title"]', 'Enterprise Evidence Page');
        await page.fill('textarea[ng-model="newPage.content"]', '# Test Content');
        await page.click('button:has-text("Save")');
        await page.waitForTimeout(3000);
    } else {
        console.log('Add Page button not found. Assuming add form is inline.');
    }
    await page.screenshot({ path: path.join(OUT_DIR, '06_pages_tab.png') });

    // Open TTPs
    console.log('Testing TTPs Tab...');
    await page.click('a[heading="TTPs"]');
    await page.waitForTimeout(1000);
    const addTtpBtn = await page.$('button[ng-click="addTtp()"]');
    if (addTtpBtn) {
        // Not filling out complex form to avoid brittle selectors, just opening it
        await addTtpBtn.click();
        await page.waitForTimeout(500);
    }
    await page.screenshot({ path: path.join(OUT_DIR, '07_ttps_tab.png') });

    // Close case via enterprise header
    console.log('Testing Close Case Action...');
    await page.click('a[heading="Details"]');
    await page.waitForTimeout(1000);
    const closeBtn = await page.$('a[ng-click="openCloseDialog()"]');
    if (closeBtn) {
        await closeBtn.click();
        await page.waitForTimeout(1000);
        await page.screenshot({ path: path.join(OUT_DIR, '08_close_dialog.png') });
    }

    console.log('Enterprise UI Validation Completed!');
    await browser.close();
})();
