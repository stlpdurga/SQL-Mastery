(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const navToggle = document.querySelector('[data-nav-toggle]');
  const navMenu = document.querySelector('[data-nav-menu]');

  navToggle?.addEventListener('click', () => {
    const open = navMenu.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', String(open));
    navToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  });

  document.querySelector('[data-register-form]')?.addEventListener('submit', (event) => {
    const password = document.querySelector('#new-password');
    const confirm = document.querySelector('#confirm-password');
    const hint = document.querySelector('[data-password-hint]');
    if (password.value !== confirm.value) {
      event.preventDefault();
      confirm.setCustomValidity('Passwords do not match.');
      confirm.reportValidity();
      hint.textContent = 'Passwords do not match.';
      hint.classList.add('quiz-feedback-bad');
    } else {
      confirm.setCustomValidity('');
      hint.textContent = 'Use at least 8 characters.';
      hint.classList.remove('quiz-feedback-bad');
    }
  });
  document.querySelector('#confirm-password')?.addEventListener('input', (event) => event.currentTarget.setCustomValidity(''));

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
    return data;
  }

  document.querySelectorAll('[data-practice-task]').forEach((button) => {
    button.addEventListener('click', () => {
      const editor = document.querySelector('[data-sql-editor]');
      if (!editor) return;
      editor.value = button.dataset.practiceTask;
      editor.focus();
      const position = editor.value.length;
      editor.setSelectionRange(position, position);
    });
  });

  document.querySelector('[data-run-query]')?.addEventListener('click', async (event) => {
    const panel = event.currentTarget.closest('[data-practice]');
    const editor = panel.querySelector('[data-sql-editor]');
    const output = panel.querySelector('[data-query-result]');
    const button = event.currentTarget;
    button.disabled = true;
    output.replaceChildren();
    try {
      const data = await postJson('/api/practice', { lesson_id: panel.dataset.lessonId, query: editor.value });
      const message = document.createElement('p');
      message.className = 'result-message';
      message.textContent = `${data.row_count} row${data.row_count === 1 ? '' : 's'} returned. Practice saved.`;
      output.append(message);
      if (data.columns.length) {
        const wrap = document.createElement('div');
        wrap.className = 'result-table-wrap';
        const table = document.createElement('table');
        table.className = 'result-table';
        const head = table.createTHead().insertRow();
        data.columns.forEach((column) => { const cell = document.createElement('th'); cell.textContent = column; head.append(cell); });
        const body = table.createTBody();
        data.rows.forEach((row) => {
          const tr = body.insertRow();
          row.forEach((value) => { const cell = tr.insertCell(); cell.textContent = value == null ? 'NULL' : String(value); });
        });
        wrap.append(table);
        output.append(wrap);
      }
    } catch (error) {
      const message = document.createElement('p');
      message.className = 'result-message error';
      message.textContent = error.message;
      output.append(message);
    } finally {
      button.disabled = false;
    }
  });

  document.querySelector('[data-submit-quiz]')?.addEventListener('click', async (event) => {
    const panel = event.currentTarget.closest('[data-quiz]');
    const answer = panel.querySelector('input[name="answer"]:checked');
    const output = panel.querySelector('[data-quiz-result]');
    if (!answer) {
      output.textContent = 'Choose an answer first.';
      output.className = 'quiz-feedback-bad';
      return;
    }
    event.currentTarget.disabled = true;
    try {
      const data = await postJson('/api/quiz', { lesson_id: panel.dataset.lessonId, answer: answer.value });
      output.textContent = data.correct ? 'Correct!' : `Not quite. Correct answer: ${data.correct_answer}`;
      output.className = data.correct ? 'quiz-feedback-good' : 'quiz-feedback-bad';
    } catch (error) {
      output.textContent = error.message;
      output.className = 'quiz-feedback-bad';
    } finally {
      event.currentTarget.disabled = false;
    }
  });

  document.querySelector('[data-complete-lesson]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await postJson('/api/lesson/complete', { lesson_id: button.dataset.lessonId });
      button.textContent = 'Completed ✓';
      button.classList.remove('button-primary');
      button.classList.add('button-complete');
      button.disabled = true;
      button.closest('.lesson-finish').querySelector('p').textContent = 'You’ve completed this lesson. Revisit it any time.';
    } catch (error) {
      button.disabled = false;
      window.alert(error.message);
    }
  });
})();
