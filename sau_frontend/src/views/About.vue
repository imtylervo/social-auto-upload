<template>
  <div class="about">
    <el-card class="about-card">
      <div class="about-header">
        <h1>Social Media Automation System</h1>
        <p class="version">social-auto-upload</p>
      </div>

      <el-divider />

      <div class="about-section">
        <h3>Overview</h3>
        <p>
          This system is an automation tool that helps content creators and operators publish video content to several major Chinese and international social media platforms in one click.
          It supports video upload, scheduled publishing and more.
        </p>
      </div>

      <div class="about-section">
        <h3>Supported Platforms</h3>
        <div class="platform-tags">
          <el-tag type="danger">Douyin</el-tag>
          <el-tag type="success">Kuaishou</el-tag>
          <el-tag type="warning">WeChat Channels</el-tag>
          <el-tag type="info">Xiaohongshu</el-tag>
        </div>
      </div>

      <div class="about-section">
        <h3>Core Features</h3>
        <ul class="feature-list">
          <li>Multi-platform account management and login state upkeep</li>
          <li>Video material upload and management</li>
          <li>One-click publishing to several platforms</li>
          <li>Scheduled publishing and batch publishing</li>
          <li>Cookie import and export</li>
        </ul>
      </div>

      <div class="about-section">
        <h3>Tech Stack</h3>
        <div class="tech-tags">
          <el-tag effect="plain">Vue 3</el-tag>
          <el-tag effect="plain">Element Plus</el-tag>
          <el-tag effect="plain">Pinia</el-tag>
          <el-tag effect="plain">Flask</el-tag>
          <el-tag effect="plain">Playwright</el-tag>
          <el-tag effect="plain">SQLite</el-tag>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
// About page component
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.about {
  max-width: 700px;
  margin: 0 auto;

  .about-card {
    .about-header {
      text-align: center;

      h1 {
        color: $text-primary;
        margin: 0 0 8px 0;
        font-size: 24px;
      }

      .version {
        color: $text-secondary;
        font-size: 14px;
        margin: 0;
      }
    }

    .about-section {
      margin-bottom: 24px;

      h3 {
        font-size: 16px;
        color: $text-primary;
        margin: 0 0 12px 0;
      }

      p {
        color: $text-secondary;
        line-height: 1.8;
        margin: 0;
      }

      .platform-tags,
      .tech-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .feature-list {
        margin: 0;
        padding-left: 20px;
        color: $text-secondary;
        line-height: 2;
      }
    }
  }
}
</style>
