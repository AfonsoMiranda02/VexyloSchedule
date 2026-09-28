document.addEventListener('DOMContentLoaded', function() {
    // A navbar do AdminLTE (Jazzmin) tem ul.navbar-nav.ml-auto no topo à direita
    var navbarRight = document.querySelector('.main-header .navbar-nav.ml-auto');
    
    if (navbarRight) {
        var li = document.createElement('li');
        li.className = 'nav-item';
        
        var a = document.createElement('a');
        a.className = 'nav-link';
        a.href = '#';
        a.id = 'theme-toggle-btn';
        a.setAttribute('role', 'button');
        
        var icon = document.createElement('i');
        icon.className = 'fas fa-moon';
        icon.id = 'theme-toggle-icon';
        
        a.appendChild(icon);
        li.appendChild(a);
        
        // Inserir antes do perfil de utilizador (que costuma ser o último)
        navbarRight.insertBefore(li, navbarRight.firstChild);
        
        // Check current state from localStorage
        var isDarkMode = localStorage.getItem('vexylo_dark_mode') === 'true';
        if (isDarkMode) {
            document.body.classList.add('dark-mode');
            icon.className = 'fas fa-sun';
        } else {
            document.body.classList.remove('dark-mode');
            icon.className = 'fas fa-moon';
        }
        
        a.addEventListener('click', function(e) {
            e.preventDefault();
            document.body.classList.toggle('dark-mode');
            
            if (document.body.classList.contains('dark-mode')) {
                icon.className = 'fas fa-sun';
                localStorage.setItem('vexylo_dark_mode', 'true');
            } else {
                icon.className = 'fas fa-moon';
                localStorage.setItem('vexylo_dark_mode', 'false');
            }
        });
    }
});
