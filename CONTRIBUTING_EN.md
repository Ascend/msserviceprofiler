# Contributing to MindStudio ServiceProfiler

Thank you for considering a contribution to MindStudio ServiceProfiler (msServiceProfiler)! We welcome contributions of any form, including bug fixes, feature enhancements, documentation improvements, and so on, or even just feedback. Whether you are an experienced developer or a first-time open source contributor, your help is highly valuable.

You can support this project in several ways:

- Report issues through [Issues](https://gitcode.com/Ascend/msserviceprofiler/issues).
- Suggest or implement new features.
- Improve or extend the documentation.
- Review Pull Requests and assist other contributors.
- Spread the word: share msServiceProfiler in blog posts or on social media, or give the repository a star.

## Finding Issues to Contribute

Want to start contributing? Check the following types of issues:

- [Good first issues](https://gitcode.com/Ascend/msserviceprofiler/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22)
- [Call for contribution](https://gitcode.com/Ascend/msserviceprofiler/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22help%20wanted%22)

In addition, you can view the [Issues list](https://gitcode.com/Ascend/msserviceprofiler/issues) to learn about the project development plans and roadmap.

## Contribution Process

### Environment Requirements

- For hardware environment requirements, see the [Ascend Product Form Description](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).
- Install the CANN open source version in advance.
- Python 3.10 or later
- CMake 3.11 or later

### Development and Testing

1. Click the "Fork" button in the upper right corner of the repository on the GitCode platform to clone the repository to your personal account.

2. Clone to local:

   ```bash
   git clone https://gitcode.com/<your-username>/msserviceprofiler.git
   cd msserviceprofiler
   ```

3. Develop code in your personal repository

   Follow the [Code Standards](#code-standards) for code development.

4. Code Testing

   See [Code Testing](#code-testing).

5. Installation Testing

   Perform an installation test on the completed code. For detailed steps, see the [msServiceProfiler Installation Guide](docs/zh/msserviceprofiler_install_guide.md).

6. Documentation Development

   If you add, change, or remove features, provide relevant documentation. For detailed documentation writing requirements, see [Documentation Development](#documentation-development).

7. Submit a Pull Request

   See [Pull Request Submission Process](#pull-request-submission-process).

### Code Standards

#### Python Code Standards

- Follow the PEP 8 coding standard.
- Use 4 spaces for indentation.
- Use PascalCase for class names (such as `DataManager`).
- Use snake_case for function and variable names (such as `parse_data`).
- Add necessary type annotations and docstrings.

#### C++ Code Standards

- Follow the existing coding style of the project.
- Use 4 spaces for indentation.
- Use PascalCase for class names.
- Use camelCase for function names.
- Add necessary comments to explain complex logic.

### Code Testing

#### Running Tests

Before submitting code, ensure that all tests pass:

   ```bash
   # Python unit tests
   cd msserviceprofiler/test
   bash run_ut.sh ms_service_profiler # or bash run_ut.sh ms_serviceparam_optimizer or bash run_ut.sh msservice_advisor

   # C++ unit tests
   cd msserviceprofiler/test
   bash run_ut.sh cpp
   ```

#### Adding Tests

- Add corresponding unit tests for new features.
- Ensure that tests cover the main logic branches.
- Test cases should have good readability and maintainability.
- Place test data in the appropriate locations under the `test/` directory.

#### Code Coverage

The coverage report is located at `${CURRENT_DIR}/coverage/coverage.xml`, where `CURRENT_DIR` is the directory of the currently executing run_ut.sh script (that is, the test directory).

### Documentation Development

#### Documentation Paths

If your changes affect how users use the product, update the relevant documentation:

- User guides: `docs/zh/`
- API documentation: docstrings in code comments
- Sample code: `samples/`

#### Documentation Standards

- Use clear and concise expressions.
- Provide complete sample code.
- Include necessary screenshots or diagram explanations.
- Ensure that links are valid.

### Pull Request Submission Process

#### Pre-Submission Checklist

Before submitting a Pull Request, ensure that:

- [ ] The code follows the project coding standards.
- [ ] Necessary test cases have been added.
- [ ] All tests pass.
- [ ] Relevant documentation has been updated.
- [ ] The commit message is clear and specific.
- [ ] The code has been self-reviewed.

#### Submission Process

1. **Create a branch**

   ```bash
   git checkout -b feature/<your-feature-name>
   ```

2. **Commit changes**

   ```bash
   git add .
   git commit -m "feat: <your feature description>"
   ```

3. **Push to the remote repository**

   ```bash
   git push origin feature/<your-feature-name>
   ```

4. **Create a Pull Request**

   Create a Pull Request on GitCode and fill in:

   1. A clear title

      Follow the [Commit Message Standards](#commit-message-standards).

   2. A detailed description

      Include the change content, reason, testing status, and so on.

   3. Link related issues

5. **Code review**

   1. After submitting a Pull Request, notify the relevant reviewers (Reviewers and Committers) to conduct a content review.
   2. Modify the code based on review feedback and resubmit the update. This process may involve multiple iterations. Maintain active response and communication.

   The Pull Request process indicates the relevant reviewers. You can assign reviewers in the Pull Request process, or contact us through the suggestions and discussion section in the [README](README.md#).

6. **Code merge**

   A Pull Request must collect the following four labels in sequence to complete the code merge:

   1. ascend-cla/yes: CLA check. For first-time development, complete the CLA signing. After completion, this label is automatically granted for each submission.
   2. ci-pipeline-passed: CI pipeline. Trigger by commenting `compile` in the Pull Request process. If the CI pipeline check fails, modify the code based on the prompts and resubmit.
   3. lgtm: Provided by Reviewers. After Reviewers approve, they comment `/lgtm` in the Pull Request process to trigger the lgtm label.
   4. approved: Provided by Committers. After Committers approve, they comment `/approved` in the Pull Request process to trigger the approved label.

   When your Pull Request collects all four labels, your PR will be merged into the main branch.

#### Pull Request Best Practices

- Keep the PR size moderate for easy review.
- One PR should address only one issue or implement one feature.
- Respond to review comments promptly.
- Keep synchronized with the main branch and resolve conflicts promptly.

#### Commit Message Standards

Commit messages should clearly describe the content and reason for changes:

```text
<type>: <subject>

<body>

<footer>
```

Types include:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `style`: Code format adjustment (does not affect functionality)
- `refactor`: Code refactoring
- `test`: Test related
- `chore`: Build process or auxiliary tool changes

Sample:

```text
feat: Add memory usage analysis feature

- Implement memory data collection module
- Add memory usage trend analysis algorithm
- Update related documentation

Closes #123
```

## Community Guidelines

### Code of Conduct

We are committed to providing a friendly, safe, and inclusive environment for all participants. By participating in this project, you agree to:

- Respect different viewpoints and experiences.
- Accept constructive criticism.
- Focus on what is best for the community.
- Show empathy toward other community members.

### Communication Channels

- **Issues**: Used to report bugs, suggest features, and discuss technical issues.
- **Pull Requests**: Used for code review and discussing specific implementations.
- **WeChat group**: Daily communication and quick Q&A (see the suggestions and discussion section in the [README](README.md)).

## License

By contributing code to this project, you agree that your contributions will be licensed under the project license. See the [LICENSE](LICENSE) file for details.

Documents under the docs directory of the msServiceProfiler tool are licensed under CC-BY 4.0. See [docs/LICENSE](./docs/LICENSE) for details.

## Acknowledgments

Thank you for your contributions to msServiceProfiler. Your efforts make this project stronger and more user-friendly. We look forward to your participation!

---

If you have any questions or need help, feel free to ask in [Issues](https://gitcode.com/Ascend/msserviceprofiler/issues) or contact us through other community channels.
