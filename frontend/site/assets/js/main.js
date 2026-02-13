/**
 * Munin Journal - 主脚本
 * 简单交互功能
 */

(function() {
    'use strict';

    // 回到顶部按钮
    const backToTopBtn = document.getElementById('backToTop');
    
    if (backToTopBtn) {
        // 监听滚动事件
        let ticking = false;
        
        function updateBackToTop() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > 300) {
                backToTopBtn.classList.add('visible');
            } else {
                backToTopBtn.classList.remove('visible');
            }
            
            ticking = false;
        }
        
        window.addEventListener('scroll', function() {
            if (!ticking) {
                window.requestAnimationFrame(updateBackToTop);
                ticking = true;
            }
        }, { passive: true });
        
        // 点击回到顶部
        backToTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // 平滑滚动（处理锚点链接）
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // 图片懒加载优化（如果浏览器支持 loading="lazy"）
    if ('loading' in HTMLImageElement.prototype) {
        // 浏览器原生支持，无需额外处理
    } else {
        // 简单回退：立即加载所有图片
        document.querySelectorAll('img[loading="lazy"]').forEach(img => {
            img.removeAttribute('loading');
        });
    }

    // 预留：主题切换功能（可扩展）
    // 如需添加暗黑模式，取消下面代码的注释并完善样式
    /*
    const themeToggle = document.getElementById('themeToggle');
    
    if (themeToggle) {
        // 从 localStorage 读取主题偏好
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
            document.documentElement.classList.add('dark-theme');
        }
        
        themeToggle.addEventListener('click', function() {
            document.documentElement.classList.toggle('dark-theme');
            const isDark = document.documentElement.classList.contains('dark-theme');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        });
    }
    */

    // 预留：搜索功能（可扩展）
    /*
    const searchInput = document.getElementById('searchInput');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function(e) {
            const query = e.target.value.toLowerCase();
            // 实现搜索逻辑
        }, 300));
    }
    */

    // 工具函数：防抖
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // 工具函数：节流
    function throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // 页面加载完成后添加 loaded 类（用于入场动画）
    window.addEventListener('DOMContentLoaded', function() {
        document.body.classList.add('loaded');
    });

    // 控制台欢迎信息
    console.log('%c📝 Munin Journal', 'font-size: 20px; font-weight: bold; color: #6366f1;');
    console.log('%c记录生活，留存时光', 'font-size: 12px; color: #71717a;');

})();
