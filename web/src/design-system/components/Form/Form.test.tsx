import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { initI18n } from '../../../i18n'
import { PasswordField, Select, TextField } from './fields'

initI18n()

describe('form fields', () => {
  it('associates label, hint and error with the input', () => {
    render(<TextField label="Email" hint="We never share it" error="Required" name="email" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const described = input.getAttribute('aria-describedby')!.split(' ')
    const texts = described.map((id) => document.getElementById(id)?.textContent)
    expect(texts).toEqual(expect.arrayContaining(['Required', 'We never share it']))
    expect(screen.getByRole('alert')).toHaveTextContent('Required')
  })

  it('password field toggles visibility with an accessible control', async () => {
    render(<PasswordField label="Password" name="password" />)
    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('type', 'password')
    const toggle = screen.getByRole('button', { name: /إظهار كلمة المرور|show password/i })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(toggle)
    expect(input).toHaveAttribute('type', 'text')
  })

  it('select is labelled', () => {
    render(
      <Select label="Type">
        <option value="a">A</option>
      </Select>,
    )
    expect(screen.getByLabelText('Type')).toBeInTheDocument()
  })
})
