# Disclaimer

## General

PyLanShare is provided **"as is"**, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

## Data Transfer & Loss

PyLanShare is designed to synchronize files between devices on a local area network. While the application employs SHA-256 hash verification and integrity checks to ensure data accuracy, **no guarantee is made that data will be transferred without errors or loss**. Users are solely responsible for maintaining independent backups of their data.

The synchronization process may **overwrite or delete files** on the receiving machine to match the sender's directory state. This is by design. The authors are not responsible for any unintended data loss resulting from misconfiguration, accidental use, or software defects.

## Network Security

PyLanShare supports optional TLS encryption and password authentication. However:

- The application is intended for use on **trusted local networks only**.
- Without TLS enabled, all data is transmitted **unencrypted** over the network.
- Password authentication uses a simple shared-secret mechanism and is **not a substitute for enterprise-grade security**.
- The authors make no guarantees regarding the security of data in transit or at rest.
- Users are responsible for ensuring that their network environment is appropriately secured.

**Do not use PyLanShare to transfer sensitive, confidential, or regulated data without first evaluating whether the security measures meet your requirements.**

## Third-Party Dependencies

PyLanShare relies on third-party open-source libraries (PySide6, websockets, watchdog, and others). The authors of PyLanShare are not responsible for any vulnerabilities, bugs, or issues introduced by these dependencies. Users should review the licenses and security advisories of all dependencies independently.

## Platform Compatibility

PyLanShare is primarily developed and tested on **Windows**. While it may function on other operating systems, no guarantee of compatibility, stability, or feature parity is made for platforms other than Windows.

## No Professional Advice

This software is a utility tool and does not constitute professional advice of any kind. It should not be used as a replacement for professional IT infrastructure, backup solutions, or file management systems in critical or production environments without proper evaluation.

## Limitation of Liability

To the maximum extent permitted by applicable law, in no event shall the authors, contributors, or distributors of PyLanShare be held liable for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services, loss of use, data, or profits, or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this software, even if advised of the possibility of such damage.

## Acceptance

By downloading, installing, or using PyLanShare, you acknowledge that you have read, understood, and agree to the terms of this disclaimer.

---

*Last updated: March 2026*
