/**
 * ANTI MATRIX — Client-Side Interactions & Dynamic Loaders
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Drawer Toggle
  const mobileToggle = document.querySelector('.mobile-toggle');
  const navLinks = document.querySelector('.nav-links');
  const navActions = document.querySelector('.nav-actions');

  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      const isVisible = navLinks.style.display === 'flex';
      navLinks.style.display = isVisible ? 'none' : 'flex';
      if (navActions) navActions.style.display = isVisible ? 'none' : 'flex';
      
      if (!isVisible) {
        navLinks.style.flexDirection = 'column';
        navLinks.style.position = 'absolute';
        navLinks.style.top = '72px';
        navLinks.style.left = '0';
        navLinks.style.width = '100%';
        navLinks.style.background = 'var(--bg-surface)';
        navLinks.style.padding = '1.5rem';
        navLinks.style.borderBottom = '1px solid var(--border-medium)';
      }
    });
  }

  // 2. Dynamic College Department Cascading Loader
  const collegeSelect = document.getElementById('college_id');
  const departmentSelect = document.getElementById('department_id');

  if (collegeSelect && departmentSelect) {
    collegeSelect.addEventListener('change', async (e) => {
      const collegeId = e.target.value;
      if (!collegeId) return;

      departmentSelect.innerHTML = '<option value="">Loading departments...</option>';
      departmentSelect.disabled = true;

      try {
        const response = await fetch(`/auth/api/departments/${collegeId}`);
        const departments = await response.json();

        departmentSelect.innerHTML = '';
        if (departments.length === 0) {
          departmentSelect.innerHTML = '<option value="">No departments found</option>';
        } else {
          departments.forEach(dept => {
            const option = document.createElement('option');
            option.value = dept.id;
            option.textContent = dept.name;
            departmentSelect.appendChild(option);
          });
        }
      } catch (err) {
        console.error('Error fetching departments:', err);
        departmentSelect.innerHTML = '<option value="">Error loading departments</option>';
      } finally {
        departmentSelect.disabled = false;
      }
    });
  }

  // 3. Auto Dismiss Alerts
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.5s ease';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });
});
