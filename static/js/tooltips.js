class TooltipManager {
  constructor() {
    this.init();
  }

  init() {
    // Find all elements with data-tooltip attribute
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
      this.createTooltip(element);
    });
  }

  createTooltip(element) {
    // Create tooltip container
    const container = document.createElement('div');
    container.className = 'tooltip-container';
    
    // Get tooltip content and position
    const content = element.getAttribute('data-tooltip');
    const position = element.getAttribute('data-tooltip-position') || 'top';
    
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = `tooltip tooltip-${position}`;
    tooltip.textContent = content;
    
    // Wrap element with container and add tooltip
    element.parentNode.insertBefore(container, element);
    container.appendChild(element);
    container.appendChild(tooltip);
    
    // Add keyboard accessibility
    element.setAttribute('tabindex', '0');
    
    // Add aria attributes for accessibility
    element.setAttribute('aria-describedby', 'tooltip');
    tooltip.setAttribute('role', 'tooltip');
  }
}

// Initialize tooltips when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.tooltipManager = new TooltipManager();
});
