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

  // 3. Portal Sidebar Off-Canvas Drawer Toggle
  const sidebar = document.getElementById('portalSidebar') || document.querySelector('.portal-sidebar');
  const toggleBtns = document.querySelectorAll('#sidebarToggleBtn, .sidebar-toggle-btn');
  const closeBtn = document.getElementById('sidebarCloseBtn') || document.querySelector('.sidebar-close-btn');
  const backdrop = document.getElementById('sidebarBackdrop') || document.querySelector('.sidebar-backdrop');

  function openPortalSidebar() {
    if (sidebar) sidebar.classList.add('is-open');
    if (backdrop) backdrop.classList.add('is-open');
    document.body.classList.add('sidebar-active');
  }

  function closePortalSidebar() {
    if (sidebar) sidebar.classList.remove('is-open');
    if (backdrop) backdrop.classList.remove('is-open');
    document.body.classList.remove('sidebar-active');
  }

  if (toggleBtns.length > 0) {
    toggleBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (sidebar && sidebar.classList.contains('is-open')) {
          closePortalSidebar();
        } else {
          openPortalSidebar();
        }
      });
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closePortalSidebar();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', () => {
      closePortalSidebar();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
      closePortalSidebar();
    }
  });

  // 4. Auto Dismiss Alerts
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.5s ease';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });
});

