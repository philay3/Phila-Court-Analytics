import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { JudgeDisclosure } from './JudgeDisclosure.js';

function renderDisclosure() {
  return render(
    <JudgeDisclosure>
      <p>judge control region</p>
    </JudgeDisclosure>,
  );
}

function trigger(): HTMLButtonElement {
  return screen.getByRole('button', {
    name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText,
  }) as HTMLButtonElement;
}

describe('JudgeDisclosure', () => {
  it('renders a native button named by the sanctioned trigger string alone, default closed', () => {
    renderDisclosure();

    const button = trigger();
    expect(button.tagName).toBe('BUTTON');
    // Never a submit button — the homepage placement is inside a form.
    expect(button).toHaveAttribute('type', 'button');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('judge control region')).not.toBeVisible();
  });

  it('wires aria-controls to the content wrapper and hides it with the hidden attribute', () => {
    renderDisclosure();

    const controlsId = trigger().getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();
    const content = document.getElementById(controlsId as string);
    expect(content).not.toBeNull();
    expect(content).toHaveAttribute('hidden');
  });

  it('opens on click (content visible, aria-expanded true) and closes again on a second click', () => {
    renderDisclosure();

    fireEvent.click(trigger());
    expect(trigger()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('judge control region')).toBeVisible();

    fireEvent.click(trigger());
    expect(trigger()).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('judge control region')).not.toBeVisible();
  });
});
